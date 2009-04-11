
import time
from zope.interface import implements
from twisted.trial import unittest
from twisted.internet import defer
from allmydata import uri, dirnode
from allmydata.immutable import upload
from allmydata.interfaces import IURI, IClient, IMutableFileNode, \
     INewDirectoryURI, IReadonlyNewDirectoryURI, IFileNode, \
     ExistingChildError, NoSuchChildError, \
     IDeepCheckResults, IDeepCheckAndRepairResults
from allmydata.mutable.filenode import MutableFileNode
from allmydata.mutable.common import UncoordinatedWriteError
from allmydata.util import hashutil, base32
from allmydata.monitor import Monitor
from allmydata.test.common import make_chk_file_uri, make_mutable_file_uri, \
     FakeDirectoryNode, create_chk_filenode, ErrorMixin
from allmydata.test.no_network import GridTestMixin
from allmydata.check_results import CheckResults, CheckAndRepairResults
import common_util as testutil

# to test dirnode.py, we want to construct a tree of real DirectoryNodes that
# contain pointers to fake files. We start with a fake MutableFileNode that
# stores all of its data in a static table.

class Marker:
    implements(IFileNode, IMutableFileNode) # sure, why not
    def __init__(self, nodeuri):
        if not isinstance(nodeuri, str):
            nodeuri = nodeuri.to_string()
        self.nodeuri = nodeuri
        si = hashutil.tagged_hash("tag1", nodeuri)[:16]
        self.storage_index = si
        fp = hashutil.tagged_hash("tag2", nodeuri)
        self.verifieruri = uri.SSKVerifierURI(storage_index=si, fingerprint=fp)
    def get_uri(self):
        return self.nodeuri
    def get_readonly_uri(self):
        return self.nodeuri
    def get_verify_cap(self):
        return self.verifieruri
    def get_storage_index(self):
        return self.storage_index

    def check(self, monitor, verify=False, add_lease=False):
        r = CheckResults(uri.from_string(self.nodeuri), None)
        r.set_healthy(True)
        r.set_recoverable(True)
        return defer.succeed(r)

    def check_and_repair(self, monitor, verify=False, add_lease=False):
        d = self.check(verify)
        def _got(cr):
            r = CheckAndRepairResults(None)
            r.pre_repair_results = r.post_repair_results = cr
            return r
        d.addCallback(_got)
        return d

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


class Dirnode(unittest.TestCase,
              testutil.ShouldFailMixin, testutil.StallMixin, ErrorMixin):
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
            d = dn.set_uri(u"child", u.to_string(), {})
            d.addCallback(lambda res: dn.list())
            def _check1(children):
                self.failUnless(u"child" in children)
            d.addCallback(_check1)
            d.addCallback(lambda res:
                          self.shouldFail(NoSuchChildError, "get bogus", None,
                                          dn.get, u"bogus"))
            def _corrupt(res):
                filenode = dn._node
                si = IURI(filenode.get_uri()).storage_index
                old_contents = filenode.all_contents[si]
                # We happen to know that the writecap MAC is near the end of the string. Flip
                # one of its bits and make sure we ignore the corruption.
                new_contents = testutil.flip_bit(old_contents, -10)
                # TODO: also test flipping bits in the other portions
                filenode.all_contents[si] = new_contents
            d.addCallback(_corrupt)
            def _check2(res):
                d = dn.list()
                def _c3(res):
                    self.failUnless(res.has_key('child'))
                d.addCallback(_c3)
            d.addCallback(_check2)
            return d
        d.addCallback(_created)
        return d

    def test_check(self):
        d = self.client.create_empty_dirnode()
        d.addCallback(lambda dn: dn.check(Monitor()))
        def _done(res):
            self.failUnless(res.is_healthy())
        d.addCallback(_done)
        return d

    def _test_deepcheck_create(self):
        # create a small tree with a loop, and some non-directories
        #  root/
        #  root/subdir/
        #  root/subdir/file1
        #  root/subdir/link -> root
        #  root/rodir
        d = self.client.create_empty_dirnode()
        def _created_root(rootnode):
            self._rootnode = rootnode
            return rootnode.create_empty_directory(u"subdir")
        d.addCallback(_created_root)
        def _created_subdir(subdir):
            self._subdir = subdir
            d = subdir.add_file(u"file1", upload.Data("data", None))
            d.addCallback(lambda res: subdir.set_node(u"link", self._rootnode))
            d.addCallback(lambda res: self.client.create_empty_dirnode())
            d.addCallback(lambda dn:
                          self._rootnode.set_uri(u"rodir",
                                                 dn.get_readonly_uri()))
            return d
        d.addCallback(_created_subdir)
        def _done(res):
            return self._rootnode
        d.addCallback(_done)
        return d

    def test_deepcheck(self):
        d = self._test_deepcheck_create()
        d.addCallback(lambda rootnode: rootnode.start_deep_check().when_done())
        def _check_results(r):
            self.failUnless(IDeepCheckResults.providedBy(r))
            c = r.get_counters()
            self.failUnlessEqual(c,
                                 {"count-objects-checked": 4,
                                  "count-objects-healthy": 4,
                                  "count-objects-unhealthy": 0,
                                  "count-objects-unrecoverable": 0,
                                  "count-corrupt-shares": 0,
                                  })
            self.failIf(r.get_corrupt_shares())
            self.failUnlessEqual(len(r.get_all_results()), 4)
        d.addCallback(_check_results)
        return d

    def test_deepcheck_and_repair(self):
        d = self._test_deepcheck_create()
        d.addCallback(lambda rootnode:
                      rootnode.start_deep_check_and_repair().when_done())
        def _check_results(r):
            self.failUnless(IDeepCheckAndRepairResults.providedBy(r))
            c = r.get_counters()
            self.failUnlessEqual(c,
                                 {"count-objects-checked": 4,
                                  "count-objects-healthy-pre-repair": 4,
                                  "count-objects-unhealthy-pre-repair": 0,
                                  "count-objects-unrecoverable-pre-repair": 0,
                                  "count-corrupt-shares-pre-repair": 0,
                                  "count-objects-healthy-post-repair": 4,
                                  "count-objects-unhealthy-post-repair": 0,
                                  "count-objects-unrecoverable-post-repair": 0,
                                  "count-corrupt-shares-post-repair": 0,
                                  "count-repairs-attempted": 0,
                                  "count-repairs-successful": 0,
                                  "count-repairs-unsuccessful": 0,
                                  })
            self.failIf(r.get_corrupt_shares())
            self.failIf(r.get_remaining_corrupt_shares())
            self.failUnlessEqual(len(r.get_all_results()), 4)
        d.addCallback(_check_results)
        return d

    def _mark_file_bad(self, rootnode):
        si = IURI(rootnode.get_uri())._filenode_uri.storage_index
        rootnode._node.bad_shares[si] = "unhealthy"
        return rootnode

    def test_deepcheck_problems(self):
        d = self._test_deepcheck_create()
        d.addCallback(lambda rootnode: self._mark_file_bad(rootnode))
        d.addCallback(lambda rootnode: rootnode.start_deep_check().when_done())
        def _check_results(r):
            c = r.get_counters()
            self.failUnlessEqual(c,
                                 {"count-objects-checked": 4,
                                  "count-objects-healthy": 3,
                                  "count-objects-unhealthy": 1,
                                  "count-objects-unrecoverable": 0,
                                  "count-corrupt-shares": 0,
                                  })
            #self.failUnlessEqual(len(r.get_problems()), 1) # TODO
        d.addCallback(_check_results)
        return d

    def test_readonly(self):
        fileuri = make_chk_file_uri(1234)
        filenode = self.client.create_node_from_uri(fileuri)
        uploadable = upload.Data("some data", convergence="some convergence string")

        d = self.client.create_empty_dirnode()
        def _created(rw_dn):
            d2 = rw_dn.set_uri(u"child", fileuri.to_string())
            d2.addCallback(lambda res: rw_dn)
            return d2
        d.addCallback(_created)

        def _ready(rw_dn):
            ro_uri = rw_dn.get_readonly_uri()
            ro_dn = self.client.create_node_from_uri(ro_uri)
            self.failUnless(ro_dn.is_readonly())
            self.failUnless(ro_dn.is_mutable())

            self.shouldFail(dirnode.NotMutableError, "set_uri ro", None,
                            ro_dn.set_uri, u"newchild", fileuri.to_string())
            self.shouldFail(dirnode.NotMutableError, "set_uri ro", None,
                            ro_dn.set_node, u"newchild", filenode)
            self.shouldFail(dirnode.NotMutableError, "set_nodes ro", None,
                            ro_dn.set_nodes, [ (u"newchild", filenode) ])
            self.shouldFail(dirnode.NotMutableError, "set_uri ro", None,
                            ro_dn.add_file, u"newchild", uploadable)
            self.shouldFail(dirnode.NotMutableError, "set_uri ro", None,
                            ro_dn.delete, u"child")
            self.shouldFail(dirnode.NotMutableError, "set_uri ro", None,
                            ro_dn.create_empty_directory, u"newchild")
            self.shouldFail(dirnode.NotMutableError, "set_metadata_for ro", None,
                            ro_dn.set_metadata_for, u"child", {})
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

    def test_create(self):
        self.expected_manifest = []
        self.expected_verifycaps = set()
        self.expected_storage_indexes = set()

        d = self.client.create_empty_dirnode()
        def _then(n):
            # /
            self.failUnless(n.is_mutable())
            u = n.get_uri()
            self.failUnless(u)
            self.failUnless(u.startswith("URI:DIR2:"), u)
            u_ro = n.get_readonly_uri()
            self.failUnless(u_ro.startswith("URI:DIR2-RO:"), u_ro)
            u_v = n.get_verify_cap().to_string()
            self.failUnless(u_v.startswith("URI:DIR2-Verifier:"), u_v)
            u_r = n.get_repair_cap().to_string()
            self.failUnlessEqual(u_r, u)
            self.expected_manifest.append( ((), u) )
            self.expected_verifycaps.add(u_v)
            si = n.get_storage_index()
            self.expected_storage_indexes.add(base32.b2a(si))
            expected_si = n._uri._filenode_uri.storage_index
            self.failUnlessEqual(si, expected_si)

            d = n.list()
            d.addCallback(lambda res: self.failUnlessEqual(res, {}))
            d.addCallback(lambda res: n.has_child(u"missing"))
            d.addCallback(lambda res: self.failIf(res))
            fake_file_uri = make_mutable_file_uri()
            other_file_uri = make_mutable_file_uri()
            m = Marker(fake_file_uri)
            ffu_v = m.get_verify_cap().to_string()
            self.expected_manifest.append( ((u"child",) , m.get_uri()) )
            self.expected_verifycaps.add(ffu_v)
            self.expected_storage_indexes.add(base32.b2a(m.get_storage_index()))
            d.addCallback(lambda res: n.set_uri(u"child", fake_file_uri.to_string()))
            d.addCallback(lambda res:
                          self.shouldFail(ExistingChildError, "set_uri-no",
                                          "child 'child' already exists",
                                          n.set_uri, u"child", other_file_uri.to_string(),
                                          overwrite=False))
            # /
            # /child = mutable

            d.addCallback(lambda res: n.create_empty_directory(u"subdir"))

            # /
            # /child = mutable
            # /subdir = directory
            def _created(subdir):
                self.failUnless(isinstance(subdir, FakeDirectoryNode))
                self.subdir = subdir
                new_v = subdir.get_verify_cap().to_string()
                assert isinstance(new_v, str)
                self.expected_manifest.append( ((u"subdir",), subdir.get_uri()) )
                self.expected_verifycaps.add(new_v)
                si = subdir.get_storage_index()
                self.expected_storage_indexes.add(base32.b2a(si))
            d.addCallback(_created)

            d.addCallback(lambda res:
                          self.shouldFail(ExistingChildError, "mkdir-no",
                                          "child 'subdir' already exists",
                                          n.create_empty_directory, u"subdir",
                                          overwrite=False))

            d.addCallback(lambda res: n.list())
            d.addCallback(lambda children:
                          self.failUnlessEqual(sorted(children.keys()),
                                               sorted([u"child", u"subdir"])))

            d.addCallback(lambda res: n.start_deep_stats().when_done())
            def _check_deepstats(stats):
                self.failUnless(isinstance(stats, dict))
                expected = {"count-immutable-files": 0,
                            "count-mutable-files": 1,
                            "count-literal-files": 0,
                            "count-files": 1,
                            "count-directories": 2,
                            "size-immutable-files": 0,
                            "size-literal-files": 0,
                            #"size-directories": 616, # varies
                            #"largest-directory": 616,
                            "largest-directory-children": 2,
                            "largest-immutable-file": 0,
                            }
                for k,v in expected.iteritems():
                    self.failUnlessEqual(stats[k], v,
                                         "stats[%s] was %s, not %s" %
                                         (k, stats[k], v))
                self.failUnless(stats["size-directories"] > 500,
                                stats["size-directories"])
                self.failUnless(stats["largest-directory"] > 500,
                                stats["largest-directory"])
                self.failUnlessEqual(stats["size-files-histogram"], [])
            d.addCallback(_check_deepstats)

            d.addCallback(lambda res: n.build_manifest().when_done())
            def _check_manifest(res):
                manifest = res["manifest"]
                self.failUnlessEqual(sorted(manifest),
                                     sorted(self.expected_manifest))
                stats = res["stats"]
                _check_deepstats(stats)
                self.failUnlessEqual(self.expected_verifycaps,
                                     res["verifycaps"])
                self.failUnlessEqual(self.expected_storage_indexes,
                                     res["storage-index"])
            d.addCallback(_check_manifest)

            def _add_subsubdir(res):
                return self.subdir.create_empty_directory(u"subsubdir")
            d.addCallback(_add_subsubdir)
            # /
            # /child = mutable
            # /subdir = directory
            # /subdir/subsubdir = directory
            d.addCallback(lambda res: n.get_child_at_path(u"subdir/subsubdir"))
            d.addCallback(lambda subsubdir:
                          self.failUnless(isinstance(subsubdir,
                                                     FakeDirectoryNode)))
            d.addCallback(lambda res: n.get_child_at_path(u""))
            d.addCallback(lambda res: self.failUnlessEqual(res.get_uri(),
                                                           n.get_uri()))

            d.addCallback(lambda res: n.get_metadata_for(u"child"))
            d.addCallback(lambda metadata:
                          self.failUnlessEqual(set(metadata.keys()),
                                               set(["tahoe", "ctime", "mtime"])))

            d.addCallback(lambda res:
                          self.shouldFail(NoSuchChildError, "gcamap-no",
                                          "nope",
                                          n.get_child_and_metadata_at_path,
                                          u"subdir/nope"))
            d.addCallback(lambda res:
                          n.get_child_and_metadata_at_path(u""))
            def _check_child_and_metadata1(res):
                child, metadata = res
                self.failUnless(isinstance(child, FakeDirectoryNode))
                # edge-metadata needs at least one path segment
                self.failUnlessEqual(sorted(metadata.keys()), [])
            d.addCallback(_check_child_and_metadata1)
            d.addCallback(lambda res:
                          n.get_child_and_metadata_at_path(u"child"))

            def _check_child_and_metadata2(res):
                child, metadata = res
                self.failUnlessEqual(child.get_uri(),
                                     fake_file_uri.to_string())
                self.failUnlessEqual(set(metadata.keys()),
                                     set(["tahoe", "ctime", "mtime"]))
            d.addCallback(_check_child_and_metadata2)

            d.addCallback(lambda res:
                          n.get_child_and_metadata_at_path(u"subdir/subsubdir"))
            def _check_child_and_metadata3(res):
                child, metadata = res
                self.failUnless(isinstance(child, FakeDirectoryNode))
                self.failUnlessEqual(set(metadata.keys()),
                                     set(["tahoe", "ctime", "mtime"]))
            d.addCallback(_check_child_and_metadata3)

            # set_uri + metadata
            # it should be possible to add a child without any metadata
            d.addCallback(lambda res: n.set_uri(u"c2", fake_file_uri.to_string(), {}))
            d.addCallback(lambda res: n.get_metadata_for(u"c2"))
            d.addCallback(lambda metadata: self.failUnlessEqual(metadata.keys(), ['tahoe']))

            # You can't override the link timestamps.
            d.addCallback(lambda res: n.set_uri(u"c2", fake_file_uri.to_string(), { 'tahoe': {'linkcrtime': "bogus"}}))
            d.addCallback(lambda res: n.get_metadata_for(u"c2"))
            def _has_good_linkcrtime(metadata):
                self.failUnless(metadata.has_key('tahoe'))
                self.failUnless(metadata['tahoe'].has_key('linkcrtime'))
                self.failIfEqual(metadata['tahoe']['linkcrtime'], 'bogus')
            d.addCallback(_has_good_linkcrtime)

            # if we don't set any defaults, the child should get timestamps
            d.addCallback(lambda res: n.set_uri(u"c3", fake_file_uri.to_string()))
            d.addCallback(lambda res: n.get_metadata_for(u"c3"))
            d.addCallback(lambda metadata:
                          self.failUnlessEqual(set(metadata.keys()),
                                               set(["tahoe", "ctime", "mtime"])))

            # or we can add specific metadata at set_uri() time, which
            # overrides the timestamps
            d.addCallback(lambda res: n.set_uri(u"c4", fake_file_uri.to_string(),
                                                {"key": "value"}))
            d.addCallback(lambda res: n.get_metadata_for(u"c4"))
            d.addCallback(lambda metadata:
                              self.failUnless((set(metadata.keys()) == set(["key", "tahoe"])) and 
                                              (metadata['key'] == "value"), metadata))

            d.addCallback(lambda res: n.delete(u"c2"))
            d.addCallback(lambda res: n.delete(u"c3"))
            d.addCallback(lambda res: n.delete(u"c4"))

            # set_node + metadata
            # it should be possible to add a child without any metadata
            d.addCallback(lambda res: n.set_node(u"d2", n, {}))
            d.addCallback(lambda res: self.client.create_empty_dirnode())
            d.addCallback(lambda n2:
                          self.shouldFail(ExistingChildError, "set_node-no",
                                          "child 'd2' already exists",
                                          n.set_node, u"d2", n2,
                                          overwrite=False))
            d.addCallback(lambda res: n.get_metadata_for(u"d2"))
            d.addCallback(lambda metadata: self.failUnlessEqual(metadata.keys(), ['tahoe']))

            # if we don't set any defaults, the child should get timestamps
            d.addCallback(lambda res: n.set_node(u"d3", n))
            d.addCallback(lambda res: n.get_metadata_for(u"d3"))
            d.addCallback(lambda metadata:
                          self.failUnlessEqual(set(metadata.keys()),
                                               set(["tahoe", "ctime", "mtime"])))

            # or we can add specific metadata at set_node() time, which
            # overrides the timestamps
            d.addCallback(lambda res: n.set_node(u"d4", n,
                                                {"key": "value"}))
            d.addCallback(lambda res: n.get_metadata_for(u"d4"))
            d.addCallback(lambda metadata:
                          self.failUnless((set(metadata.keys()) == set(["key", "tahoe"])) and 
                                          (metadata['key'] == "value"), metadata))

            d.addCallback(lambda res: n.delete(u"d2"))
            d.addCallback(lambda res: n.delete(u"d3"))
            d.addCallback(lambda res: n.delete(u"d4"))

            # metadata through set_children()
            d.addCallback(lambda res: n.set_children([ (u"e1", fake_file_uri.to_string()),
                                                   (u"e2", fake_file_uri.to_string(), {}),
                                                   (u"e3", fake_file_uri.to_string(),
                                                    {"key": "value"}),
                                                   ]))
            d.addCallback(lambda res:
                          self.shouldFail(ExistingChildError, "set_children-no",
                                          "child 'e1' already exists",
                                          n.set_children,
                                          [ (u"e1", other_file_uri),
                                            (u"new", other_file_uri), ],
                                          overwrite=False))
            # and 'new' should not have been created
            d.addCallback(lambda res: n.list())
            d.addCallback(lambda children: self.failIf(u"new" in children))
            d.addCallback(lambda res: n.get_metadata_for(u"e1"))
            d.addCallback(lambda metadata:
                          self.failUnlessEqual(set(metadata.keys()),
                                               set(["tahoe", "ctime", "mtime"])))
            d.addCallback(lambda res: n.get_metadata_for(u"e2"))
            d.addCallback(lambda metadata: 
                          self.failUnlessEqual(set(metadata.keys()), set(['tahoe'])))
            d.addCallback(lambda res: n.get_metadata_for(u"e3"))
            d.addCallback(lambda metadata:
                              self.failUnless((set(metadata.keys()) == set(["key", "tahoe"])) 
                                              and (metadata['key'] == "value"), metadata))

            d.addCallback(lambda res: n.delete(u"e1"))
            d.addCallback(lambda res: n.delete(u"e2"))
            d.addCallback(lambda res: n.delete(u"e3"))

            # metadata through set_nodes()
            d.addCallback(lambda res: n.set_nodes([ (u"f1", n),
                                                    (u"f2", n, {}),
                                                    (u"f3", n,
                                                     {"key": "value"}),
                                                    ]))
            d.addCallback(lambda res:
                          self.shouldFail(ExistingChildError, "set_nodes-no",
                                          "child 'f1' already exists",
                                          n.set_nodes,
                                          [ (u"f1", n),
                                            (u"new", n), ],
                                          overwrite=False))
            # and 'new' should not have been created
            d.addCallback(lambda res: n.list())
            d.addCallback(lambda children: self.failIf(u"new" in children))
            d.addCallback(lambda res: n.get_metadata_for(u"f1"))
            d.addCallback(lambda metadata:
                          self.failUnlessEqual(set(metadata.keys()),
                                               set(["tahoe", "ctime", "mtime"])))
            d.addCallback(lambda res: n.get_metadata_for(u"f2"))
            d.addCallback(
                lambda metadata: self.failUnlessEqual(set(metadata.keys()), set(['tahoe'])))
            d.addCallback(lambda res: n.get_metadata_for(u"f3"))
            d.addCallback(lambda metadata:
                              self.failUnless((set(metadata.keys()) == set(["key", "tahoe"])) and 
                                              (metadata['key'] == "value"), metadata))

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
                                                 upload.Data("stamp me", convergence="some convergence string")))
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
                          self.failUnlessEqual(set(metadata.keys()),
                                               set(["tahoe", "ctime", "mtime"])))
            d.addCallback(lambda res: n.delete(u"no_timestamps"))

            d.addCallback(lambda res: n.delete(u"subdir"))
            d.addCallback(lambda old_child:
                          self.failUnlessEqual(old_child.get_uri(),
                                               self.subdir.get_uri()))

            d.addCallback(lambda res: n.list())
            d.addCallback(lambda children:
                          self.failUnlessEqual(sorted(children.keys()),
                                               sorted([u"child"])))

            uploadable = upload.Data("some data", convergence="some convergence string")
            d.addCallback(lambda res: n.add_file(u"newfile", uploadable))
            d.addCallback(lambda newnode:
                          self.failUnless(IFileNode.providedBy(newnode)))
            other_uploadable = upload.Data("some data", convergence="stuff")
            d.addCallback(lambda res:
                          self.shouldFail(ExistingChildError, "add_file-no",
                                          "child 'newfile' already exists",
                                          n.add_file, u"newfile",
                                          other_uploadable,
                                          overwrite=False))
            d.addCallback(lambda res: n.list())
            d.addCallback(lambda children:
                          self.failUnlessEqual(sorted(children.keys()),
                                               sorted([u"child", u"newfile"])))
            d.addCallback(lambda res: n.get_metadata_for(u"newfile"))
            d.addCallback(lambda metadata:
                          self.failUnlessEqual(set(metadata.keys()),
                                               set(["tahoe", "ctime", "mtime"])))

            d.addCallback(lambda res: n.add_file(u"newfile-metadata",
                                                 uploadable,
                                                 {"key": "value"}))
            d.addCallback(lambda newnode:
                          self.failUnless(IFileNode.providedBy(newnode)))
            d.addCallback(lambda res: n.get_metadata_for(u"newfile-metadata"))
            d.addCallback(lambda metadata:
                              self.failUnless((set(metadata.keys()) == set(["key", "tahoe"])) and 
                                              (metadata['key'] == "value"), metadata))
            d.addCallback(lambda res: n.delete(u"newfile-metadata"))

            d.addCallback(lambda res: n.create_empty_directory(u"subdir2"))
            def _created2(subdir2):
                self.subdir2 = subdir2
                # put something in the way, to make sure it gets overwritten
                return subdir2.add_file(u"child", upload.Data("overwrite me",
                                                              "converge"))
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
            d.addCallback(lambda res: self.subdir2.get(u"child"))
            d.addCallback(lambda child:
                          self.failUnlessEqual(child.get_uri(),
                                               fake_file_uri.to_string()))

            # move it back, using new_child_name=
            d.addCallback(lambda res:
                          self.subdir2.move_child_to(u"child", n, u"newchild"))
            d.addCallback(lambda res: n.list())
            d.addCallback(lambda children:
                          self.failUnlessEqual(sorted(children.keys()),
                                               sorted([u"newchild", u"newfile",
                                                       u"subdir2"])))
            d.addCallback(lambda res: self.subdir2.list())
            d.addCallback(lambda children:
                          self.failUnlessEqual(sorted(children.keys()), []))

            # now make sure that we honor overwrite=False
            d.addCallback(lambda res:
                          self.subdir2.set_uri(u"newchild", other_file_uri.to_string()))

            d.addCallback(lambda res:
                          self.shouldFail(ExistingChildError, "move_child_to-no",
                                          "child 'newchild' already exists",
                                          n.move_child_to, u"newchild",
                                          self.subdir2,
                                          overwrite=False))
            d.addCallback(lambda res: self.subdir2.get(u"newchild"))
            d.addCallback(lambda child:
                          self.failUnlessEqual(child.get_uri(),
                                               other_file_uri.to_string()))

            return d

        d.addCallback(_then)

        d.addErrback(self.explain_error)
        return d

class DeepStats(unittest.TestCase):
    def test_stats(self):
        ds = dirnode.DeepStats(None)
        ds.add("count-files")
        ds.add("size-immutable-files", 123)
        ds.histogram("size-files-histogram", 123)
        ds.max("largest-directory", 444)

        s = ds.get_results()
        self.failUnlessEqual(s["count-files"], 1)
        self.failUnlessEqual(s["size-immutable-files"], 123)
        self.failUnlessEqual(s["largest-directory"], 444)
        self.failUnlessEqual(s["count-literal-files"], 0)

        ds.add("count-files")
        ds.add("size-immutable-files", 321)
        ds.histogram("size-files-histogram", 321)
        ds.max("largest-directory", 2)

        s = ds.get_results()
        self.failUnlessEqual(s["count-files"], 2)
        self.failUnlessEqual(s["size-immutable-files"], 444)
        self.failUnlessEqual(s["largest-directory"], 444)
        self.failUnlessEqual(s["count-literal-files"], 0)
        self.failUnlessEqual(s["size-files-histogram"],
                             [ (101, 316, 1), (317, 1000, 1) ])

        ds = dirnode.DeepStats(None)
        for i in range(1, 1100):
            ds.histogram("size-files-histogram", i)
        ds.histogram("size-files-histogram", 4*1000*1000*1000*1000) # 4TB
        s = ds.get_results()
        self.failUnlessEqual(s["size-files-histogram"],
                             [ (1, 3, 3),
                               (4, 10, 7),
                               (11, 31, 21),
                               (32, 100, 69),
                               (101, 316, 216),
                               (317, 1000, 684),
                               (1001, 3162, 99),
                               (3162277660169L, 10000000000000L, 1),
                               ])

class UCWEingMutableFileNode(MutableFileNode):
    please_ucwe_after_next_upload = False

    def _upload(self, new_contents, servermap):
        d = MutableFileNode._upload(self, new_contents, servermap)
        def _ucwe(res):
            if self.please_ucwe_after_next_upload:
                self.please_ucwe_after_next_upload = False
                raise UncoordinatedWriteError()
            return res
        d.addCallback(_ucwe)
        return d
class UCWEingNewDirectoryNode(dirnode.NewDirectoryNode):
    filenode_class = UCWEingMutableFileNode


class Deleter(GridTestMixin, unittest.TestCase):
    def test_retry(self):
        # ticket #550, a dirnode.delete which experiences an
        # UncoordinatedWriteError will fail with an incorrect "you're
        # deleting something which isn't there" NoSuchChildError exception.

        # to trigger this, we start by creating a directory with a single
        # file in it. Then we create a special dirnode that uses a modified
        # MutableFileNode which will raise UncoordinatedWriteError once on
        # demand. We then call dirnode.delete, which ought to retry and
        # succeed.

        self.basedir = self.mktemp()
        self.set_up_grid()
        c0 = self.g.clients[0]
        d = c0.create_empty_dirnode()
        small = upload.Data("Small enough for a LIT", None)
        def _created_dir(dn):
            self.root = dn
            self.root_uri = dn.get_uri()
            return dn.add_file(u"file", small)
        d.addCallback(_created_dir)
        def _do_delete(ignored):
            n = UCWEingNewDirectoryNode(c0).init_from_uri(self.root_uri)
            assert n._node.please_ucwe_after_next_upload == False
            n._node.please_ucwe_after_next_upload = True
            # This should succeed, not raise an exception
            return n.delete(u"file")
        d.addCallback(_do_delete)

        return d

