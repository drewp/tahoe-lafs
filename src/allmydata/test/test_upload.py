
import os
from twisted.trial import unittest
from twisted.python.failure import Failure
from twisted.python import log
from twisted.internet import defer
from cStringIO import StringIO

from allmydata import upload, encode, uri
from allmydata.interfaces import IFileURI
from allmydata.util.assertutil import precondition
from foolscap import eventual

MiB = 1024*1024

class Uploadable(unittest.TestCase):
    def shouldEqual(self, data, expected):
        self.failUnless(isinstance(data, list))
        for e in data:
            self.failUnless(isinstance(e, str))
        s = "".join(data)
        self.failUnlessEqual(s, expected)

    def test_filehandle(self):
        s = StringIO("a"*41)
        u = upload.FileHandle(s)
        d = u.get_size()
        d.addCallback(self.failUnlessEqual, 41)
        d.addCallback(lambda res: u.read(1))
        d.addCallback(self.shouldEqual, "a")
        d.addCallback(lambda res: u.read(80))
        d.addCallback(self.shouldEqual, "a"*40)
        d.addCallback(lambda res: u.close()) # this doesn't close the filehandle
        d.addCallback(lambda res: s.close()) # that privilege is reserved for us
        return d

    def test_filename(self):
        basedir = "upload/Uploadable/test_filename"
        os.makedirs(basedir)
        fn = os.path.join(basedir, "file")
        f = open(fn, "w")
        f.write("a"*41)
        f.close()
        u = upload.FileName(fn)
        d = u.get_size()
        d.addCallback(self.failUnlessEqual, 41)
        d.addCallback(lambda res: u.read(1))
        d.addCallback(self.shouldEqual, "a")
        d.addCallback(lambda res: u.read(80))
        d.addCallback(self.shouldEqual, "a"*40)
        d.addCallback(lambda res: u.close())
        return d

    def test_data(self):
        s = "a"*41
        u = upload.Data(s)
        d = u.get_size()
        d.addCallback(self.failUnlessEqual, 41)
        d.addCallback(lambda res: u.read(1))
        d.addCallback(self.shouldEqual, "a")
        d.addCallback(lambda res: u.read(80))
        d.addCallback(self.shouldEqual, "a"*40)
        d.addCallback(lambda res: u.close())
        return d

class FakePeer:
    def __init__(self, mode="good"):
        self.ss = FakeStorageServer(mode)

    def callRemote(self, methname, *args, **kwargs):
        def _call():
            meth = getattr(self, methname)
            return meth(*args, **kwargs)
        return defer.maybeDeferred(_call)

    def get_service(self, sname):
        assert sname == "storageserver"
        return self.ss

class FakeStorageServer:
    def __init__(self, mode):
        self.mode = mode
        self.allocated = []
        self.queries = 0
    def callRemote(self, methname, *args, **kwargs):
        def _call():
            meth = getattr(self, methname)
            return meth(*args, **kwargs)
        d = eventual.fireEventually()
        d.addCallback(lambda res: _call())
        return d

    def allocate_buckets(self, storage_index, renew_secret, cancel_secret,
                         sharenums, share_size, canary):
        #print "FakeStorageServer.allocate_buckets(num=%d, size=%d)" % (len(sharenums), share_size)
        self.queries += 1
        if self.mode == "full":
            return (set(), {},)
        elif self.mode == "already got them":
            return (set(sharenums), {},)
        else:
            for shnum in sharenums:
                self.allocated.append( (storage_index, shnum) )
            return (set(),
                    dict([( shnum, FakeBucketWriter(share_size) )
                          for shnum in sharenums]),
                    )

class FakeBucketWriter:
    # a diagnostic version of storageserver.BucketWriter
    def __init__(self, size):
        self.data = StringIO()
        self.closed = False
        self._size = size

    def callRemote(self, methname, *args, **kwargs):
        def _call():
            meth = getattr(self, "remote_" + methname)
            return meth(*args, **kwargs)
        d = eventual.fireEventually()
        d.addCallback(lambda res: _call())
        return d

    def remote_write(self, offset, data):
        precondition(not self.closed)
        precondition(offset >= 0)
        precondition(offset+len(data) <= self._size,
                     "offset=%d + data=%d > size=%d" %
                     (offset, len(data), self._size))
        self.data.seek(offset)
        self.data.write(data)

    def remote_close(self):
        precondition(not self.closed)
        self.closed = True

    def remote_abort(self):
        log.err("uh oh, I was asked to abort")

class FakeClient:
    DEFAULT_ENCODING_PARAMETERS = {"k":25,
                                   "happy": 75,
                                   "n": 100,
                                   "max_segment_size": 1*MiB,
                                   }
    def __init__(self, mode="good", num_servers=50):
        self.mode = mode
        self.num_servers = num_servers
    def log(self, *args, **kwargs):
        pass
    def get_permuted_peers(self, storage_index, include_myself):
        peers = [ ("%20d"%fakeid, "%20d"%fakeid, FakePeer(self.mode),)
                  for fakeid in range(self.num_servers) ]
        self.last_peers = [p[2] for p in peers]
        return peers
    def get_push_to_ourselves(self):
        return None
    def get_encoding_parameters(self):
        return self.DEFAULT_ENCODING_PARAMETERS

    def get_renewal_secret(self):
        return ""
    def get_cancel_secret(self):
        return ""

DATA = """
Once upon a time, there was a beautiful princess named Buttercup. She lived
in a magical land where every file was stored securely among millions of
machines, and nobody ever worried about their data being lost ever again.
The End.
"""
assert len(DATA) > upload.Uploader.URI_LIT_SIZE_THRESHOLD

SIZE_ZERO = 0
SIZE_SMALL = 16
SIZE_LARGE = len(DATA)

class GoodServer(unittest.TestCase):
    def setUp(self):
        self.node = FakeClient(mode="good")
        self.u = upload.Uploader()
        self.u.running = True
        self.u.parent = self.node

    def set_encoding_parameters(self, k, happy, n, max_segsize=1*MiB):
        p = {"k": k,
             "happy": happy,
             "n": n,
             "max_segment_size": max_segsize,
             }
        self.node.DEFAULT_ENCODING_PARAMETERS = p

    def _check_small(self, newuri, size):
        u = IFileURI(newuri)
        self.failUnless(isinstance(u, uri.LiteralFileURI))
        self.failUnlessEqual(len(u.data), size)

    def _check_large(self, newuri, size):
        u = IFileURI(newuri)
        self.failUnless(isinstance(u, uri.CHKFileURI))
        self.failUnless(isinstance(u.storage_index, str))
        self.failUnlessEqual(len(u.storage_index), 16)
        self.failUnless(isinstance(u.key, str))
        self.failUnlessEqual(len(u.key), 16)
        self.failUnlessEqual(u.size, size)

    def get_data(self, size):
        return DATA[:size]

    def test_data_zero(self):
        data = self.get_data(SIZE_ZERO)
        d = self.u.upload_data(data)
        d.addCallback(self._check_small, SIZE_ZERO)
        return d

    def test_data_small(self):
        data = self.get_data(SIZE_SMALL)
        d = self.u.upload_data(data)
        d.addCallback(self._check_small, SIZE_SMALL)
        return d

    def test_data_large(self):
        data = self.get_data(SIZE_LARGE)
        d = self.u.upload_data(data)
        d.addCallback(self._check_large, SIZE_LARGE)
        return d

    def test_data_large_odd_segments(self):
        data = self.get_data(SIZE_LARGE)
        segsize = int(SIZE_LARGE / 2.5)
        # we want 3 segments, since that's not a power of two
        self.set_encoding_parameters(25, 75, 100, segsize)
        d = self.u.upload_data(data)
        d.addCallback(self._check_large, SIZE_LARGE)
        return d

    def test_filehandle_zero(self):
        data = self.get_data(SIZE_ZERO)
        d = self.u.upload_filehandle(StringIO(data))
        d.addCallback(self._check_small, SIZE_ZERO)
        return d

    def test_filehandle_small(self):
        data = self.get_data(SIZE_SMALL)
        d = self.u.upload_filehandle(StringIO(data))
        d.addCallback(self._check_small, SIZE_SMALL)
        return d

    def test_filehandle_large(self):
        data = self.get_data(SIZE_LARGE)
        d = self.u.upload_filehandle(StringIO(data))
        d.addCallback(self._check_large, SIZE_LARGE)
        return d

    def test_filename_zero(self):
        fn = "Uploader-test_filename_zero.data"
        f = open(fn, "wb")
        data = self.get_data(SIZE_ZERO)
        f.write(data)
        f.close()
        d = self.u.upload_filename(fn)
        d.addCallback(self._check_small, SIZE_ZERO)
        return d

    def test_filename_small(self):
        fn = "Uploader-test_filename_small.data"
        f = open(fn, "wb")
        data = self.get_data(SIZE_SMALL)
        f.write(data)
        f.close()
        d = self.u.upload_filename(fn)
        d.addCallback(self._check_small, SIZE_SMALL)
        return d

    def test_filename_large(self):
        fn = "Uploader-test_filename_large.data"
        f = open(fn, "wb")
        data = self.get_data(SIZE_LARGE)
        f.write(data)
        f.close()
        d = self.u.upload_filename(fn)
        d.addCallback(self._check_large, SIZE_LARGE)
        return d

class FullServer(unittest.TestCase):
    def setUp(self):
        self.node = FakeClient(mode="full")
        self.u = upload.Uploader()
        self.u.running = True
        self.u.parent = self.node

    def _should_fail(self, f):
        self.failUnless(isinstance(f, Failure) and f.check(encode.NotEnoughPeersError), f)

    def test_data_large(self):
        data = DATA
        d = self.u.upload_data(data)
        d.addBoth(self._should_fail)
        return d

class PeerSelection(unittest.TestCase):

    def make_client(self, num_servers=50):
        self.node = FakeClient(mode="good", num_servers=num_servers)
        self.u = upload.Uploader()
        self.u.running = True
        self.u.parent = self.node

    def get_data(self, size):
        return DATA[:size]

    def _check_large(self, newuri, size):
        u = IFileURI(newuri)
        self.failUnless(isinstance(u, uri.CHKFileURI))
        self.failUnless(isinstance(u.storage_index, str))
        self.failUnlessEqual(len(u.storage_index), 16)
        self.failUnless(isinstance(u.key, str))
        self.failUnlessEqual(len(u.key), 16)
        self.failUnlessEqual(u.size, size)

    def set_encoding_parameters(self, k, happy, n, max_segsize=1*MiB):
        p = {"k": k,
             "happy": happy,
             "n": n,
             "max_segment_size": max_segsize,
             }
        self.node.DEFAULT_ENCODING_PARAMETERS = p

    def test_one_each(self):
        # if we have 50 shares, and there are 50 peers, and they all accept a
        # share, we should get exactly one share per peer

        self.make_client()
        data = self.get_data(SIZE_LARGE)
        self.set_encoding_parameters(25, 30, 50)
        d = self.u.upload_data(data)
        d.addCallback(self._check_large, SIZE_LARGE)
        def _check(res):
            for p in self.node.last_peers:
                allocated = p.ss.allocated
                self.failUnlessEqual(len(allocated), 1)
                self.failUnlessEqual(p.ss.queries, 1)
        d.addCallback(_check)
        return d

    def test_two_each(self):
        # if we have 100 shares, and there are 50 peers, and they all accept
        # all shares, we should get exactly two shares per peer

        self.make_client()
        data = self.get_data(SIZE_LARGE)
        self.set_encoding_parameters(50, 75, 100)
        d = self.u.upload_data(data)
        d.addCallback(self._check_large, SIZE_LARGE)
        def _check(res):
            for p in self.node.last_peers:
                allocated = p.ss.allocated
                self.failUnlessEqual(len(allocated), 2)
                self.failUnlessEqual(p.ss.queries, 2)
        d.addCallback(_check)
        return d

    def test_one_each_plus_one_extra(self):
        # if we have 51 shares, and there are 50 peers, then one peer gets
        # two shares and the rest get just one

        self.make_client()
        data = self.get_data(SIZE_LARGE)
        self.set_encoding_parameters(24, 41, 51)
        d = self.u.upload_data(data)
        d.addCallback(self._check_large, SIZE_LARGE)
        def _check(res):
            got_one = []
            got_two = []
            for p in self.node.last_peers:
                allocated = p.ss.allocated
                self.failUnless(len(allocated) in (1,2), len(allocated))
                if len(allocated) == 1:
                    self.failUnlessEqual(p.ss.queries, 1)
                    got_one.append(p)
                else:
                    self.failUnlessEqual(p.ss.queries, 2)
                    got_two.append(p)
            self.failUnlessEqual(len(got_one), 49)
            self.failUnlessEqual(len(got_two), 1)
        d.addCallback(_check)
        return d

    def test_four_each(self):
        # if we have 200 shares, and there are 50 peers, then each peer gets
        # 4 shares. The design goal is to accomplish this with only two
        # queries per peer.

        self.make_client()
        data = self.get_data(SIZE_LARGE)
        self.set_encoding_parameters(100, 150, 200)
        d = self.u.upload_data(data)
        d.addCallback(self._check_large, SIZE_LARGE)
        def _check(res):
            for p in self.node.last_peers:
                allocated = p.ss.allocated
                self.failUnlessEqual(len(allocated), 4)
                self.failUnlessEqual(p.ss.queries, 2)
        d.addCallback(_check)
        return d

    def test_three_of_ten(self):
        # if we have 10 shares and 3 servers, I want to see 3+3+4 rather than
        # 4+4+2

        self.make_client(3)
        data = self.get_data(SIZE_LARGE)
        self.set_encoding_parameters(3, 5, 10)
        d = self.u.upload_data(data)
        d.addCallback(self._check_large, SIZE_LARGE)
        def _check(res):
            counts = {}
            for p in self.node.last_peers:
                allocated = p.ss.allocated
                counts[len(allocated)] = counts.get(len(allocated), 0) + 1
            histogram = [counts.get(i, 0) for i in range(5)]
            self.failUnlessEqual(histogram, [0,0,0,2,1])
        d.addCallback(_check)
        return d


# TODO:
#  upload with exactly 75 peers (shares_of_happiness)
#  have a download fail
#  cancel a download (need to implement more cancel stuff)
