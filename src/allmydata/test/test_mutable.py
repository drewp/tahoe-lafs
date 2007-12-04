
import itertools, struct
from twisted.trial import unittest
from twisted.internet import defer
from twisted.python import failure, log
from allmydata import mutable, uri, dirnode
from allmydata.util.hashutil import tagged_hash
from allmydata.encode import NotEnoughPeersError
from allmydata.interfaces import IURI, INewDirectoryURI, \
     IMutableFileURI, IUploadable, IFileURI
from allmydata.filenode import LiteralFileNode
import sha

class FakeFilenode(mutable.MutableFileNode):
    counter = itertools.count(1)
    all_contents = {}
    all_rw_friends = {}

    def create(self, initial_contents, wait_for_numpeers=None):
        d = mutable.MutableFileNode.create(self, initial_contents, wait_for_numpeers=None)
        def _then(res):
            self.all_contents[self.get_uri()] = initial_contents
            return res
        d.addCallback(_then)
        return d
    def init_from_uri(self, myuri):
        mutable.MutableFileNode.init_from_uri(self, myuri)
        return self
    def replace(self, newdata, wait_for_numpeers=None):
        self.all_contents[self.get_uri()] = newdata
        return defer.succeed(self)
    def _generate_pubprivkeys(self):
        count = self.counter.next()
        return FakePubKey(count), FakePrivKey(count)
    def _publish(self, initial_contents, wait_for_numpeers):
        self.all_contents[self.get_uri()] = initial_contents
        return defer.succeed(self)

    def download_to_data(self):
        if self.is_readonly():
            assert self.all_rw_friends.has_key(self.get_uri()), (self.get_uri(), id(self.all_rw_friends))
            return defer.succeed(self.all_contents[self.all_rw_friends[self.get_uri()]])
        else:
            return defer.succeed(self.all_contents[self.get_uri()])
    def replace(self, newdata, wait_for_numpeers=None):
        self.all_contents[self.get_uri()] = newdata
        return defer.succeed(None)

class FakePublish(mutable.Publish):
    def _do_query(self, conn, peerid, peer_storage_servers, storage_index):
        assert conn[0] == peerid
        shares = self._peers[peerid]
        return defer.succeed(shares)

    def _do_testreadwrite(self, peerid, peer_storage_servers, secrets,
                          tw_vectors, read_vector):
        # always-pass: parrot the test vectors back to them.
        readv = {}
        for shnum, (testv, datav, new_length) in tw_vectors.items():
            for (offset, length, op, specimen) in testv:
                assert op in ("le", "eq", "ge")
            readv[shnum] = [ specimen
                             for (offset, length, op, specimen)
                             in testv ]
        answer = (True, readv)
        return defer.succeed(answer)


class FakeNewDirectoryNode(dirnode.NewDirectoryNode):
    filenode_class = FakeFilenode

class FakeIntroducerClient:
    def when_enough_peers(self, numpeers):
        return defer.succeed(None)

class FakeClient:
    def __init__(self, num_peers=10):
        self._num_peers = num_peers
        self._peerids = [tagged_hash("peerid", "%d" % i)[:20]
                         for i in range(self._num_peers)]
        self.introducer_client = FakeIntroducerClient()
    def log(self, msg, **kw):
        return log.msg(msg, **kw)

    def get_renewal_secret(self):
        return "I hereby permit you to renew my files"
    def get_cancel_secret(self):
        return "I hereby permit you to cancel my leases"

    def create_empty_dirnode(self, wait_for_numpeers):
        n = FakeNewDirectoryNode(self)
        d = n.create(wait_for_numpeers=wait_for_numpeers)
        d.addCallback(lambda res: n)
        return d

    def create_dirnode_from_uri(self, u):
        return FakeNewDirectoryNode(self).init_from_uri(u)

    def create_mutable_file(self, contents="", wait_for_numpeers=None):
        n = FakeFilenode(self)
        d = n.create(contents, wait_for_numpeers=wait_for_numpeers)
        d.addCallback(lambda res: n)
        return d

    def create_node_from_uri(self, u):
        u = IURI(u)
        if INewDirectoryURI.providedBy(u):
            return self.create_dirnode_from_uri(u)
        if IFileURI.providedBy(u):
            if isinstance(u, uri.LiteralFileURI):
                return LiteralFileNode(u, self)
            else:
                # CHK
                raise RuntimeError("not simulated")
        assert IMutableFileURI.providedBy(u), u
        res = FakeFilenode(self).init_from_uri(u)
        return res

    def get_permuted_peers(self, key, include_myself=True):
        """
        @return: list of (permuted-peerid, peerid, connection,)
        """
        peers_and_connections = [(pid, (pid,)) for pid in self._peerids]
        results = []
        for peerid, connection in peers_and_connections:
            assert isinstance(peerid, str)
            permuted = sha.new(key + peerid).digest()
            results.append((permuted, peerid, connection))
        results.sort()
        return results

    def upload(self, uploadable, wait_for_numpeers=None):
        assert IUploadable.providedBy(uploadable)
        d = uploadable.get_size()
        d.addCallback(lambda length: uploadable.read(length))
        #d.addCallback(self.create_mutable_file)
        def _got_data(datav):
            data = "".join(datav)
            #newnode = FakeFilenode(self)
            return uri.LiteralFileURI(data)
        d.addCallback(_got_data)
        return d

class Filenode(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient()

    def test_create(self):
        d = self.client.create_mutable_file(wait_for_numpeers=1)
        def _created(n):
            d = n.replace("contents 1")
            d.addCallback(lambda res: self.failUnlessIdentical(res, None))
            d.addCallback(lambda res: n.download_to_data())
            d.addCallback(lambda res: self.failUnlessEqual(res, "contents 1"))
            d.addCallback(lambda res: n.replace("contents 2"))
            d.addCallback(lambda res: n.download_to_data())
            d.addCallback(lambda res: self.failUnlessEqual(res, "contents 2"))
            return d
        d.addCallback(_created)
        return d

    def test_create_with_initial_contents(self):
        d = self.client.create_mutable_file("contents 1")
        def _created(n):
            d = n.download_to_data()
            d.addCallback(lambda res: self.failUnlessEqual(res, "contents 1"))
            d.addCallback(lambda res: n.replace("contents 2"))
            d.addCallback(lambda res: n.download_to_data())
            d.addCallback(lambda res: self.failUnlessEqual(res, "contents 2"))
            return d
        d.addCallback(_created)
        return d


class Publish(unittest.TestCase):
    def test_encrypt(self):
        c = FakeClient()
        fn = FakeFilenode(c)
        # .create usually returns a Deferred, but we happen to know it's
        # synchronous
        CONTENTS = "some initial contents"
        fn.create(CONTENTS, wait_for_numpeers=1)
        p = mutable.Publish(fn)
        target_info = None
        d = defer.maybeDeferred(p._encrypt_and_encode, target_info,
                                CONTENTS, "READKEY", "IV"*8, 3, 10)
        def _done( ((shares, share_ids),
                    required_shares, total_shares,
                    segsize, data_length, target_info2) ):
            self.failUnlessEqual(len(shares), 10)
            for sh in shares:
                self.failUnless(isinstance(sh, str))
                self.failUnlessEqual(len(sh), 7)
            self.failUnlessEqual(len(share_ids), 10)
            self.failUnlessEqual(required_shares, 3)
            self.failUnlessEqual(total_shares, 10)
            self.failUnlessEqual(segsize, 21)
            self.failUnlessEqual(data_length, len(CONTENTS))
            self.failUnlessIdentical(target_info, target_info2)
        d.addCallback(_done)
        return d

    def test_generate(self):
        c = FakeClient()
        fn = FakeFilenode(c)
        # .create usually returns a Deferred, but we happen to know it's
        # synchronous
        CONTENTS = "some initial contents"
        fn.create(CONTENTS, wait_for_numpeers=1)
        p = mutable.Publish(fn)
        r = mutable.Retrieve(fn)
        # make some fake shares
        shares_and_ids = ( ["%07d" % i for i in range(10)], range(10) )
        target_info = None
        p._privkey = FakePrivKey(0)
        p._encprivkey = "encprivkey"
        p._pubkey = FakePubKey(0)
        d = defer.maybeDeferred(p._generate_shares,
                                (shares_and_ids,
                                 3, 10,
                                 21, # segsize
                                 len(CONTENTS),
                                 target_info),
                                3, # seqnum
                                "IV"*8)
        def _done( (seqnum, root_hash, final_shares, target_info2) ):
            self.failUnlessEqual(seqnum, 3)
            self.failUnlessEqual(len(root_hash), 32)
            self.failUnless(isinstance(final_shares, dict))
            self.failUnlessEqual(len(final_shares), 10)
            self.failUnlessEqual(sorted(final_shares.keys()), range(10))
            for i,sh in final_shares.items():
                self.failUnless(isinstance(sh, str))
                self.failUnlessEqual(len(sh), 381)
                # feed the share through the unpacker as a sanity-check
                pieces = mutable.unpack_share(sh)
                (u_seqnum, u_root_hash, IV, k, N, segsize, datalen,
                 pubkey, signature, share_hash_chain, block_hash_tree,
                 share_data, enc_privkey) = pieces
                self.failUnlessEqual(u_seqnum, 3)
                self.failUnlessEqual(u_root_hash, root_hash)
                self.failUnlessEqual(k, 3)
                self.failUnlessEqual(N, 10)
                self.failUnlessEqual(segsize, 21)
                self.failUnlessEqual(datalen, len(CONTENTS))
                self.failUnlessEqual(pubkey, FakePubKey(0).serialize())
                sig_material = struct.pack(">BQ32s16s BBQQ",
                                           0, seqnum, root_hash, IV,
                                           k, N, segsize, datalen)
                self.failUnlessEqual(signature,
                                     FakePrivKey(0).sign(sig_material))
                self.failUnless(isinstance(share_hash_chain, dict))
                self.failUnlessEqual(len(share_hash_chain), 4) # ln2(10)++
                for shnum,share_hash in share_hash_chain.items():
                    self.failUnless(isinstance(shnum, int))
                    self.failUnless(isinstance(share_hash, str))
                    self.failUnlessEqual(len(share_hash), 32)
                self.failUnless(isinstance(block_hash_tree, list))
                self.failUnlessEqual(len(block_hash_tree), 1) # very small tree
                self.failUnlessEqual(IV, "IV"*8)
                self.failUnlessEqual(len(share_data), len("%07d" % 1))
                self.failUnlessEqual(enc_privkey, "encprivkey")
            self.failUnlessIdentical(target_info, target_info2)
        d.addCallback(_done)
        return d

    def setup_for_sharemap(self, num_peers):
        c = FakeClient(num_peers)
        fn = FakeFilenode(c)
        # .create usually returns a Deferred, but we happen to know it's
        # synchronous
        CONTENTS = "some initial contents"
        fn.create(CONTENTS)
        p = FakePublish(fn)
        p._storage_index = "\x00"*32
        #r = mutable.Retrieve(fn)
        p._peers = {}
        for peerid in c._peerids:
            p._peers[peerid] = {}
        return c, p

    def shouldFail(self, expected_failure, which, call, *args, **kwargs):
        substring = kwargs.pop("substring", None)
        d = defer.maybeDeferred(call, *args, **kwargs)
        def _done(res):
            if isinstance(res, failure.Failure):
                res.trap(expected_failure)
                if substring:
                    self.failUnless(substring in str(res),
                                    "substring '%s' not in '%s'"
                                    % (substring, str(res)))
            else:
                self.fail("%s was supposed to raise %s, not get '%s'" %
                          (which, expected_failure, res))
        d.addBoth(_done)
        return d

    def test_sharemap_20newpeers(self):
        c, p = self.setup_for_sharemap(20)

        total_shares = 10
        d = p._query_peers(total_shares)
        def _done(target_info):
            (target_map, shares_per_peer, peer_storage_servers) = target_info
            shares_per_peer = {}
            for shnum in target_map:
                for (peerid, old_seqnum, old_R) in target_map[shnum]:
                    #print "shnum[%d]: send to %s [oldseqnum=%s]" % \
                    #      (shnum, idlib.b2a(peerid), old_seqnum)
                    if peerid not in shares_per_peer:
                        shares_per_peer[peerid] = 1
                    else:
                        shares_per_peer[peerid] += 1
            # verify that we're sending only one share per peer
            for peerid, count in shares_per_peer.items():
                self.failUnlessEqual(count, 1)
        d.addCallback(_done)
        return d

    def test_sharemap_3newpeers(self):
        c, p = self.setup_for_sharemap(3)

        total_shares = 10
        d = p._query_peers(total_shares)
        def _done(target_info):
            (target_map, shares_per_peer, peer_storage_servers) = target_info
            shares_per_peer = {}
            for shnum in target_map:
                for (peerid, old_seqnum, old_R) in target_map[shnum]:
                    if peerid not in shares_per_peer:
                        shares_per_peer[peerid] = 1
                    else:
                        shares_per_peer[peerid] += 1
            # verify that we're sending 3 or 4 shares per peer
            for peerid, count in shares_per_peer.items():
                self.failUnless(count in (3,4), count)
        d.addCallback(_done)
        return d

    def test_sharemap_nopeers(self):
        c, p = self.setup_for_sharemap(0)

        total_shares = 10
        d = self.shouldFail(NotEnoughPeersError, "test_sharemap_nopeers",
                            p._query_peers, total_shares)
        return d

    def test_write(self):
        total_shares = 10
        c, p = self.setup_for_sharemap(20)
        p._privkey = FakePrivKey(0)
        p._encprivkey = "encprivkey"
        p._pubkey = FakePubKey(0)
        # make some fake shares
        CONTENTS = "some initial contents"
        shares_and_ids = ( ["%07d" % i for i in range(10)], range(10) )
        d = defer.maybeDeferred(p._query_peers, total_shares)
        IV = "IV"*8
        d.addCallback(lambda target_info:
                      p._generate_shares( (shares_and_ids,
                                           3, total_shares,
                                           21, # segsize
                                           len(CONTENTS),
                                           target_info),
                                          3, # seqnum
                                          IV))
        d.addCallback(p._send_shares, IV)
        def _done((surprised, dispatch_map)):
            self.failIf(surprised, "surprised!")
        d.addCallback(_done)
        return d

    def setup_for_publish(self, num_peers):
        c = FakeClient(num_peers)
        fn = FakeFilenode(c)
        # .create usually returns a Deferred, but we happen to know it's
        # synchronous
        fn.create("")
        p = FakePublish(fn)
        p._peers = {}
        for peerid in c._peerids:
            p._peers[peerid] = {}
        return c, fn, p

    def test_publish(self):
        c, fn, p = self.setup_for_publish(20)
        # make sure the length of our contents string is not a multiple of k,
        # to exercise the padding code.
        d = p.publish("New contents of the mutable filenode.")
        def _done(res):
            # TODO: examine peers and check on their shares
            pass
        d.addCallback(_done)
        return d


class FakePubKey:
    def __init__(self, count):
        self.count = count
    def serialize(self):
        return "PUBKEY-%d" % self.count
    def verify(self, msg, signature):
        return True

class FakePrivKey:
    def __init__(self, count):
        self.count = count
    def serialize(self):
        return "PRIVKEY-%d" % self.count
    def sign(self, data):
        return "SIGN(%s)" % data
