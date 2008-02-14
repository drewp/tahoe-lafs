
import time
from zope.interface import implements
from twisted.trial import unittest
from allmydata import uri, dirnode, upload
from allmydata.interfaces import IURI, IClient, IMutableFileNode, \
     INewDirectoryURI, IReadonlyNewDirectoryURI, IFileNode
from allmydata.util import hashutil, testutil
from allmydata.test.common import make_chk_file_uri, make_mutable_file_uri, \
     NonGridDirectoryNode, create_chk_filenode
from twisted.internet import defer, reactor

# to test dirnode.py, we want to construct a tree of real DirectoryNodes that
# contain pointers to fake files. We start with a fake MutableFileNode that
# stores all of its data in a static table.

FakeDirectoryNode = NonGridDirectoryNode

class Marker:
    implements(IFileNode, IMutableFileNode) # sure, why not
    def __init__(self, nodeuri):
        if not isinstance(nodeuri, str):
            nodeuri = nodeuri.to_string()
        self.nodeuri = nodeuri
        si = hashutil.tagged_hash("tag1", nodeuri)[:16]
        fp = hashutil.tagged_hash("tag2", nodeuri)
        self.verifieruri = uri.SSKVerifierURI(storage_index=si,
                                              fingerprint=fp).to_string()
    def get_uri(self):
        return self.nodeuri
    def get_readonly_uri(self):
        return self.nodeuri
    def get_verifier(self):
        return self.verifieruri

# dirnode requires three methods from the client: upload(),
# create_node_from_uri(), and create_empty_dirnode(). Of these, upload() is
# only used by the convenience composite method add_file().

class FakeClient:
    implements(IClient)

    def upload(self, uploadable):
        d = uploadable.get_size()
        d.addCallback(lambda size: uploadable.read(size))
        def _got_data(datav):
            data = "".join(datav)
            n = create_chk_filenode(self, data)
            results = upload.UploadResults()
            results.uri = n.get_uri()
            return results
        d.addCallback(_got_data)
        return d

    def create_node_from_uri(self, u):
        u = IURI(u)
        if (INewDirectoryURI.providedBy(u)
            or IReadonlyNewDirectoryURI.providedBy(u)):
            return FakeDirectoryNode(self).init_from_uri(u)
        return Marker(u.to_string())

    def create_empty_dirnode(self):
        n = FakeDirectoryNode(self)
        d = n.create()
        d.addCallback(lambda res: n)
        return d


class Dirnode(unittest.TestCase, testutil.ShouldFailMixin):
    def setUp(self):
        self.client = FakeClient()

    def test_basic(self):
        d = self.client.create_empty_dirnode()
        def _done(res):
            self.failUnless(isinstance(res, FakeDirectoryNode))
            rep = str(res)
            self.failUnless("RW" in rep)
        d.addCallback(_done)
        return d

    def test_corrupt(self):
        d = self.client.create_empty_dirnode()
        def _created(dn):
            u = make_mutable_file_uri()
            d = dn.set_uri(u"child", u, {})
            d.addCallback(lambda res: dn.list())
            def _check1(children):
                self.failUnless(u"child" in children)
            d.addCallback(_check1)
            d.addCallback(lambda res:
                          self.shouldFail(KeyError, "get bogus", None,
                                          dn.get, u"bogus"))
            def _corrupt(res):
                filenode = dn._node
                si = IURI(filenode.get_uri()).storage_index
                old_contents = filenode.all_contents[si]
                # we happen to know that the writecap is encrypted near the
                # end of the string. Flip one of its bits and make sure we
                # detect the corruption.
                new_contents = testutil.flip_bit(old_contents, -10)
                # TODO: also test flipping bits in the other portions
                filenode.all_contents[si] = new_contents
            d.addCallback(_corrupt)
            def _check2(res):
                self.shouldFail(hashutil.IntegrityCheckError, "corrupt",
                                "HMAC does not match, crypttext is corrupted",
                                dn.list)
            d.addCallback(_check2)
            return d
        d.addCallback(_created)
        return d

    def test_check(self):
        d = self.client.create_empty_dirnode()
        d.addCallback(lambda dn: dn.check())
        def _done(res):
            pass
        d.addCallback(_done)
        return d

    def test_readonly(self):
        fileuri = make_chk_file_uri(1234)
        filenode = self.client.create_node_from_uri(fileuri)
        uploadable = upload.Data("some data")

        d = self.client.create_empty_dirnode()
        def _created(rw_dn):
            d2 = rw_dn.set_uri(u"child", fileuri)
            d2.addCallback(lambda res: rw_dn)
            return d2
        d.addCallback(_created)

        def _ready(rw_dn):
            ro_uri = rw_dn.get_readonly_uri()
            ro_dn = self.client.create_node_from_uri(ro_uri)
            self.failUnless(ro_dn.is_readonly())
            self.failUnless(ro_dn.is_mutable())

            self.shouldFail(dirnode.NotMutableError, "set_uri ro", None,
                            ro_dn.set_uri, u"newchild", fileuri)
            self.shouldFail(dirnode.NotMutableError, "set_uri ro", None,
                            ro_dn.set_node, u"newchild", filenode)
            self.shouldFail(dirnode.NotMutableError, "set_uri ro", None,
                            ro_dn.add_file, u"newchild", uploadable)
            self.shouldFail(dirnode.NotMutableError, "set_uri ro", None,
                            ro_dn.delete, u"child")
            self.shouldFail(dirnode.NotMutableError, "set_uri ro", None,
                            ro_dn.create_empty_directory, u"newchild")
            self.shouldFail(dirnode.NotMutableError, "set_uri ro", None,
                            ro_dn.move_child_to, u"child", rw_dn)
            self.shouldFail(dirnode.NotMutableError, "set_uri ro", None,
                            rw_dn.move_child_to, u"child", ro_dn)
            return ro_dn.list()
        d.addCallback(_ready)
        def _listed(children):
            self.failUnless(u"child" in children)
        d.addCallback(_listed)
        return d

    def failUnlessGreaterThan(self, a, b):
        self.failUnless(a > b, "%r should be > %r" % (a, b))

    def failUnlessGreaterOrEqualThan(self, a, b):
        self.failUnless(a >= b, "%r should be >= %r" % (a, b))

    def stall(self, res, delay=1.0):
        d = defer.Deferred()
        reactor.callLater(delay, d.callback, res)
        return d

    def test_create(self):
        self.expected_manifest = []

        d = self.client.create_empty_dirnode()
        def _then(n):
            self.failUnless(n.is_mutable())
            u = n.get_uri()
            self.failUnless(u)
            self.failUnless(u.startswith("URI:DIR2:"), u)
            u_ro = n.get_readonly_uri()
            self.failUnless(u_ro.startswith("URI:DIR2-RO:"), u_ro)
            u_v = n.get_verifier()
            self.failUnless(u_v.startswith("URI:DIR2-Verifier:"), u_v)
            self.expected_manifest.append(u_v)

            d = n.list()
            d.addCallback(lambda res: self.failUnlessEqual(res, {}))
            d.addCallback(lambda res: n.has_child(u"missing"))
            d.addCallback(lambda res: self.failIf(res))
            fake_file_uri = make_mutable_file_uri()
            m = Marker(fake_file_uri)
            ffu_v = m.get_verifier()
            assert isinstance(ffu_v, str)
            self.expected_manifest.append(ffu_v)
            d.addCallback(lambda res: n.set_uri(u"child", fake_file_uri))

            d.addCallback(lambda res: n.create_empty_directory(u"subdir"))
            def _created(subdir):
                self.failUnless(isinstance(subdir, FakeDirectoryNode))
                self.subdir = subdir
                new_v = subdir.get_verifier()
                assert isinstance(new_v, str)
                self.expected_manifest.append(new_v)
            d.addCallback(_created)

            d.addCallback(lambda res: n.list())
            d.addCallback(lambda children:
                          self.failUnlessEqual(sorted(children.keys()),
                                               sorted([u"child", u"subdir"])))

            d.addCallback(lambda res: n.build_manifest())
            def _check_manifest(manifest):
                self.failUnlessEqual(sorted(manifest),
                                     sorted(self.expected_manifest))
            d.addCallback(_check_manifest)

            def _add_subsubdir(res):
                return self.subdir.create_empty_directory(u"subsubdir")
            d.addCallback(_add_subsubdir)
            d.addCallback(lambda res: n.get_child_at_path(u"subdir/subsubdir"))
            d.addCallback(lambda subsubdir:
                          self.failUnless(isinstance(subsubdir,
                                                     FakeDirectoryNode)))
            d.addCallback(lambda res: n.get_child_at_path(u""))
            d.addCallback(lambda res: self.failUnlessEqual(res.get_uri(),
                                                           n.get_uri()))

            d.addCallback(lambda res: n.get_metadata_for(u"child"))
            d.addCallback(lambda metadata:
                          self.failUnlessEqual(sorted(metadata.keys()),
                                               ["ctime", "mtime"]))

            # set_uri + metadata
            # it should be possible to add a child without any metadata
            d.addCallback(lambda res: n.set_uri(u"c2", fake_file_uri, {}))
            d.addCallback(lambda res: n.get_metadata_for(u"c2"))
            d.addCallback(lambda metadata: self.failUnlessEqual(metadata, {}))

            # if we don't set any defaults, the child should get timestamps
            d.addCallback(lambda res: n.set_uri(u"c3", fake_file_uri))
            d.addCallback(lambda res: n.get_metadata_for(u"c3"))
            d.addCallback(lambda metadata:
                          self.failUnlessEqual(sorted(metadata.keys()),
                                               ["ctime", "mtime"]))

            # or we can add specific metadata at set_uri() time, which
            # overrides the timestamps
            d.addCallback(lambda res: n.set_uri(u"c4", fake_file_uri,
                                                {"key": "value"}))
            d.addCallback(lambda res: n.get_metadata_for(u"c4"))
            d.addCallback(lambda metadata:
                          self.failUnlessEqual(metadata, {"key": "value"}))

            d.addCallback(lambda res: n.delete(u"c2"))
            d.addCallback(lambda res: n.delete(u"c3"))
            d.addCallback(lambda res: n.delete(u"c4"))

            # set_node + metadata
            # it should be possible to add a child without any metadata
            d.addCallback(lambda res: n.set_node(u"d2", n, {}))
            d.addCallback(lambda res: n.get_metadata_for(u"d2"))
            d.addCallback(lambda metadata: self.failUnlessEqual(metadata, {}))

            # if we don't set any defaults, the child should get timestamps
            d.addCallback(lambda res: n.set_node(u"d3", n))
            d.addCallback(lambda res: n.get_metadata_for(u"d3"))
            d.addCallback(lambda metadata:
                          self.failUnlessEqual(sorted(metadata.keys()),
                                               ["ctime", "mtime"]))

            # or we can add specific metadata at set_node() time, which
            # overrides the timestamps
            d.addCallback(lambda res: n.set_node(u"d4", n,
                                                {"key": "value"}))
            d.addCallback(lambda res: n.get_metadata_for(u"d4"))
            d.addCallback(lambda metadata:
                          self.failUnlessEqual(metadata, {"key": "value"}))

            d.addCallback(lambda res: n.delete(u"d2"))
            d.addCallback(lambda res: n.delete(u"d3"))
            d.addCallback(lambda res: n.delete(u"d4"))

            # metadata through set_uris()
            d.addCallback(lambda res: n.set_uris([ (u"e1", fake_file_uri),
                                                   (u"e2", fake_file_uri, {}),
                                                   (u"e3", fake_file_uri,
                                                    {"key": "value"}),
                                                   ]))
            d.addCallback(lambda res: n.get_metadata_for(u"e1"))
            d.addCallback(lambda metadata:
                          self.failUnlessEqual(sorted(metadata.keys()),
                                               ["ctime", "mtime"]))
            d.addCallback(lambda res: n.get_metadata_for(u"e2"))
            d.addCallback(lambda metadata: self.failUnlessEqual(metadata, {}))
            d.addCallback(lambda res: n.get_metadata_for(u"e3"))
            d.addCallback(lambda metadata:
                          self.failUnlessEqual(metadata, {"key": "value"}))

            d.addCallback(lambda res: n.delete(u"e1"))
            d.addCallback(lambda res: n.delete(u"e2"))
            d.addCallback(lambda res: n.delete(u"e3"))

            # metadata through set_nodes()
            d.addCallback(lambda res: n.set_nodes([ (u"f1", n),
                                                    (u"f2", n, {}),
                                                    (u"f3", n,
                                                     {"key": "value"}),
                                                    ]))
            d.addCallback(lambda res: n.get_metadata_for(u"f1"))
            d.addCallback(lambda metadata:
                          self.failUnlessEqual(sorted(metadata.keys()),
                                               ["ctime", "mtime"]))
            d.addCallback(lambda res: n.get_metadata_for(u"f2"))
            d.addCallback(lambda metadata: self.failUnlessEqual(metadata, {}))
            d.addCallback(lambda res: n.get_metadata_for(u"f3"))
            d.addCallback(lambda metadata:
                          self.failUnlessEqual(metadata, {"key": "value"}))

            d.addCallback(lambda res: n.delete(u"f1"))
            d.addCallback(lambda res: n.delete(u"f2"))
            d.addCallback(lambda res: n.delete(u"f3"))


            d.addCallback(lambda res:
                          n.set_metadata_for(u"child",
                                             {"tags": ["web2.0-compatible"]}))
            d.addCallback(lambda n1: n1.get_metadata_for(u"child"))
            d.addCallback(lambda metadata:
                          self.failUnlessEqual(metadata,
                                               {"tags": ["web2.0-compatible"]}))

            def _start(res):
                self._start_timestamp = time.time()
            d.addCallback(_start)
            # simplejson-1.7.1 (as shipped on Ubuntu 'gutsy') rounds all
            # floats to hundredeths (it uses str(num) instead of repr(num)).
            # simplejson-1.7.3 does not have this bug. To prevent this bug
            # from causing the test to fail, stall for more than a few
            # hundrededths of a second.
            d.addCallback(self.stall, 0.1)
            d.addCallback(lambda res: n.add_file(u"timestamps",
                                                 upload.Data("stamp me")))
            d.addCallback(self.stall, 0.1)
            def _stop(res):
                self._stop_timestamp = time.time()
            d.addCallback(_stop)

            d.addCallback(lambda res: n.get_metadata_for(u"timestamps"))
            def _check_timestamp1(metadata):
                self.failUnless("ctime" in metadata)
                self.failUnless("mtime" in metadata)
                self.failUnlessGreaterOrEqualThan(metadata["ctime"],
                                                  self._start_timestamp)
                self.failUnlessGreaterOrEqualThan(self._stop_timestamp,
                                                  metadata["ctime"])
                self.failUnlessGreaterOrEqualThan(metadata["mtime"],
                                                  self._start_timestamp)
                self.failUnlessGreaterOrEqualThan(self._stop_timestamp,
                                                  metadata["mtime"])
                # Our current timestamp rules say that replacing an existing
                # child should preserve the 'ctime' but update the mtime
                self._old_ctime = metadata["ctime"]
                self._old_mtime = metadata["mtime"]
            d.addCallback(_check_timestamp1)
            d.addCallback(self.stall, 2.0) # accomodate low-res timestamps
            d.addCallback(lambda res: n.set_node(u"timestamps", n))
            d.addCallback(lambda res: n.get_metadata_for(u"timestamps"))
            def _check_timestamp2(metadata):
                self.failUnlessEqual(metadata["ctime"], self._old_ctime,
                                     "%s != %s" % (metadata["ctime"],
                                                   self._old_ctime))
                self.failUnlessGreaterThan(metadata["mtime"], self._old_mtime)
                return n.delete(u"timestamps")
            d.addCallback(_check_timestamp2)

            # also make sure we can add/update timestamps on a
            # previously-existing child that didn't have any, since there are
            # a lot of 0.7.0-generated edges around out there
            d.addCallback(lambda res: n.set_node(u"no_timestamps", n, {}))
            d.addCallback(lambda res: n.set_node(u"no_timestamps", n))
            d.addCallback(lambda res: n.get_metadata_for(u"no_timestamps"))
            d.addCallback(lambda metadata:
                          self.failUnlessEqual(sorted(metadata.keys()),
                                               ["ctime", "mtime"]))
            d.addCallback(lambda res: n.delete(u"no_timestamps"))

            d.addCallback(lambda res: n.delete(u"subdir"))
            d.addCallback(lambda old_child:
                          self.failUnlessEqual(old_child.get_uri(),
                                               self.subdir.get_uri()))

            d.addCallback(lambda res: n.list())
            d.addCallback(lambda children:
                          self.failUnlessEqual(sorted(children.keys()),
                                               sorted([u"child"])))

            uploadable = upload.Data("some data")
            d.addCallback(lambda res: n.add_file(u"newfile", uploadable))
            d.addCallback(lambda newnode:
                          self.failUnless(IFileNode.providedBy(newnode)))
            d.addCallback(lambda res: n.list())
            d.addCallback(lambda children:
                          self.failUnlessEqual(sorted(children.keys()),
                                               sorted([u"child", u"newfile"])))
            d.addCallback(lambda res: n.get_metadata_for(u"newfile"))
            d.addCallback(lambda metadata:
                          self.failUnlessEqual(sorted(metadata.keys()),
                                               ["ctime", "mtime"]))

            uploadable = upload.Data("some data")
            d.addCallback(lambda res: n.add_file(u"newfile-metadata",
                                                 uploadable,
                                                 {"key": "value"}))
            d.addCallback(lambda newnode:
                          self.failUnless(IFileNode.providedBy(newnode)))
            d.addCallback(lambda res: n.get_metadata_for(u"newfile-metadata"))
            d.addCallback(lambda metadata:
                          self.failUnlessEqual(metadata, {"key": "value"}))
            d.addCallback(lambda res: n.delete(u"newfile-metadata"))

            d.addCallback(lambda res: n.create_empty_directory(u"subdir2"))
            def _created2(subdir2):
                self.subdir2 = subdir2
            d.addCallback(_created2)

            d.addCallback(lambda res:
                          n.move_child_to(u"child", self.subdir2))
            d.addCallback(lambda res: n.list())
            d.addCallback(lambda children:
                          self.failUnlessEqual(sorted(children.keys()),
                                               sorted([u"newfile", u"subdir2"])))
            d.addCallback(lambda res: self.subdir2.list())
            d.addCallback(lambda children:
                          self.failUnlessEqual(sorted(children.keys()),
                                               sorted([u"child"])))

            return d

        d.addCallback(_then)

        return d


netstring = hashutil.netstring
split_netstring = dirnode.split_netstring

class Netstring(unittest.TestCase):
    def test_split(self):
        a = netstring("hello") + netstring("world")
        self.failUnlessEqual(split_netstring(a, 2), ("hello", "world"))
        self.failUnlessEqual(split_netstring(a, 2, False), ("hello", "world"))
        self.failUnlessEqual(split_netstring(a, 2, True),
                             ("hello", "world", ""))
        self.failUnlessRaises(ValueError, split_netstring, a, 3)
        self.failUnlessRaises(ValueError, split_netstring, a+" extra", 2)
        self.failUnlessRaises(ValueError, split_netstring, a+" extra", 2, False)

    def test_extra(self):
        a = netstring("hello")
        self.failUnlessEqual(split_netstring(a, 1, True), ("hello", ""))
        b = netstring("hello") + "extra stuff"
        self.failUnlessEqual(split_netstring(b, 1, True),
                             ("hello", "extra stuff"))

    def test_nested(self):
        a = netstring("hello") + netstring("world") + "extra stuff"
        b = netstring("a") + netstring("is") + netstring(a) + netstring(".")
        top = split_netstring(b, 4)
        self.failUnlessEqual(len(top), 4)
        self.failUnlessEqual(top[0], "a")
        self.failUnlessEqual(top[1], "is")
        self.failUnlessEqual(top[2], a)
        self.failUnlessEqual(top[3], ".")
        self.failUnlessRaises(ValueError, split_netstring, a, 2)
        self.failUnlessRaises(ValueError, split_netstring, a, 2, False)
        bottom = split_netstring(a, 2, True)
        self.failUnlessEqual(bottom, ("hello", "world", "extra stuff"))

