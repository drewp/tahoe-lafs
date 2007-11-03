
import os, struct
from zope.interface import implements
from twisted.internet import defer
from allmydata.interfaces import IMutableFileNode, IMutableFileURI
from allmydata.util import hashutil, mathutil
from allmydata.uri import WriteableSSKFileURI
from allmydata.Crypto.Cipher import AES
from allmydata import hashtree, codec


HEADER_LENGTH = struct.calcsize(">BQ32s BBQQ LLLLLQQ")

class NeedMoreDataError(Exception):
    def __init__(self, needed_bytes):
        Exception.__init__(self)
        self.needed_bytes = needed_bytes


# use client.create_mutable_file() to make one of these

class MutableFileNode:
    implements(IMutableFileNode)

    def __init__(self, client):
        self._client = client
        self._pubkey = None # filled in upon first read
        self._privkey = None # filled in if we're mutable
        self._sharemap = {} # known shares, shnum-to-nodeid

        self._current_data = None # SDMF: we're allowed to cache the contents
        self._current_roothash = None # ditto
        self._current_seqnum = None # ditto

    def init_from_uri(self, myuri):
        # we have the URI, but we have not yet retrieved the public
        # verification key, nor things like 'k' or 'N'. If and when someone
        # wants to get our contents, we'll pull from shares and fill those
        # in.
        self._uri = IMutableFileURI(myuri)
        return self

    def create(self, initial_contents):
        """Call this when the filenode is first created. This will generate
        the keys, generate the initial shares, allocate shares, and upload
        the initial contents. Returns a Deferred that fires (with the
        MutableFileNode instance you should use) when it completes.
        """
        self._privkey = "very private"
        self._pubkey = "public"
        self._writekey = hashutil.ssk_writekey_hash(self._privkey)
        self._fingerprint = hashutil.ssk_pubkey_fingerprint_hash(self._pubkey)
        self._uri = WriteableSSKFileURI(self._writekey, self._fingerprint)
        d = defer.succeed(None)
        return d


    def get_uri(self):
        return self._uri.to_string()

    def is_mutable(self):
        return self._uri.is_mutable()

    def __hash__(self):
        return hash((self.__class__, self.uri))
    def __cmp__(self, them):
        if cmp(type(self), type(them)):
            return cmp(type(self), type(them))
        if cmp(self.__class__, them.__class__):
            return cmp(self.__class__, them.__class__)
        return cmp(self.uri, them.uri)

    def get_verifier(self):
        return IMutableFileURI(self._uri).get_verifier()

    def check(self):
        verifier = self.get_verifier()
        return self._client.getServiceNamed("checker").check(verifier)

    def download(self, target):
        #downloader = self._client.getServiceNamed("downloader")
        #return downloader.download(self.uri, target)
        raise NotImplementedError

    def download_to_data(self):
        #downloader = self._client.getServiceNamed("downloader")
        #return downloader.download_to_data(self.uri)
        return defer.succeed("this isn't going to fool you, is it")

    def replace(self, newdata):
        return defer.succeed(None)

class Retrieve:

    def __init__(self, filenode):
        self._node = filenode

    def _unpack_share(self, data):
        assert len(data) >= HEADER_LENGTH
        o = {}
        (version,
         seqnum,
         root_hash,
         k, N, segsize, datalen,
         o['signature'],
         o['share_hash_chain'],
         o['block_hash_tree'],
         o['IV'],
         o['share_data'],
         o['enc_privkey'],
         o['EOF']) = struct.unpack(">BQ32s" + "BBQQ" + "LLLLLQQ",
                                         data[:HEADER_LENGTH])

        assert version == 0
        if len(data) < o['EOF']:
            raise NeedMoreDataError(o['EOF'])

        pubkey = data[HEADER_LENGTH:o['signature']]
        signature = data[o['signature']:o['share_hash_chain']]
        share_hash_chain_s = data[o['share_hash_chain']:o['block_hash_tree']]
        share_hash_format = ">H32s"
        hsize = struct.calcsize(share_hash_format)
        assert len(share_hash_chain_s) % hsize == 0, len(share_hash_chain_s)
        share_hash_chain = []
        for i in range(0, len(share_hash_chain_s), hsize):
            chunk = share_hash_chain_s[i:i+hsize]
            (hid, h) = struct.unpack(share_hash_format, chunk)
            share_hash_chain.append( (hid, h) )
        block_hash_tree_s = data[o['block_hash_tree']:o['IV']]
        assert len(block_hash_tree_s) % 32 == 0, len(block_hash_tree_s)
        block_hash_tree = []
        for i in range(0, len(block_hash_tree_s), 32):
            block_hash_tree.append(block_hash_tree_s[i:i+32])

        IV = data[o['IV']:o['share_data']]
        share_data = data[o['share_data']:o['enc_privkey']]
        enc_privkey = data[o['enc_privkey']:o['EOF']]

        return (seqnum, root_hash, k, N, segsize, datalen,
                pubkey, signature, share_hash_chain, block_hash_tree,
                IV, share_data, enc_privkey)



class Publish:
    """I represent a single act of publishing the mutable file to the grid."""

    def __init__(self, filenode):
        self._node = filenode

    def publish(self, newdata):
        """Publish the filenode's current contents. Returns a Deferred that
        fires (with None) when the publish has done as much work as it's ever
        going to do, or errbacks with ConsistencyError if it detects a
        simultaneous write."""

        # 1: generate shares (SDMF: files are small, so we can do it in RAM)
        # 2: perform peer selection, get candidate servers
        # 3: pre-allocate some shares to some servers, based upon any existing
        #    self._node._sharemap
        # 4: send allocate/testv_and_writev messages
        # 5: as responses return, update share-dispatch table
        # 5a: may need to run recovery algorithm
        # 6: when enough responses are back, we're done

        old_roothash = self._node._current_roothash
        old_seqnum = self._node._current_seqnum

        readkey = self._node.readkey
        required_shares = self._node.required_shares
        total_shares = self._node.total_shares
        privkey = self._node.privkey
        pubkey = self._node.pubkey

        d = defer.succeed(newdata)
        d.addCallback(self._encrypt_and_encode, readkey,
                      required_shares, total_shares)
        d.addCallback(self._generate_shares, old_seqnum+1,
                      privkey, self._encprivkey, pubkey)

        d.addCallback(self._get_peers)
        d.addCallback(self._map_shares)
        d.addCallback(self._send_shares)
        d.addCallback(self._wait_for_responses)
        d.addCallback(lambda res: None)
        return d

    def _encrypt_and_encode(self, newdata, readkey,
                            required_shares, total_shares):
        IV = os.urandom(16)
        key = hashutil.ssk_readkey_data_hash(IV, readkey)
        enc = AES.new(key=key, mode=AES.MODE_CTR, counterstart="\x00"*16)
        crypttext = enc.encrypt(newdata)

        # now apply FEC
        self.MAX_SEGMENT_SIZE = 1024*1024
        segment_size = min(self.MAX_SEGMENT_SIZE, len(crypttext))
        # this must be a multiple of self.required_shares
        segment_size = mathutil.next_multiple(segment_size,
                                                   required_shares)
        self.num_segments = mathutil.div_ceil(len(crypttext), segment_size)
        assert self.num_segments == 1 # SDMF restrictions
        fec = codec.CRSEncoder()
        fec.set_params(segment_size, required_shares, total_shares)
        piece_size = fec.get_block_size()
        crypttext_pieces = []
        for offset in range(0, len(crypttext), piece_size):
            piece = crypttext[offset:offset+piece_size]
            if len(piece) < piece_size:
                pad_size = piece_size - len(piece)
                piece = piece + "\x00"*pad_size
            crypttext_pieces.append(piece)
            assert len(piece) == piece_size

        d = fec.encode(crypttext_pieces)
        d.addCallback(lambda shares:
                      (shares, required_shares, total_shares,
                       segment_size, len(crypttext), IV) )
        return d

    def _generate_shares(self, (shares_and_shareids,
                                required_shares, total_shares,
                                segment_size, data_length, IV),
                         seqnum, privkey, encprivkey, pubkey):

        (shares, share_ids) = shares_and_shareids

        assert len(shares) == len(share_ids)
        assert len(shares) == total_shares
        all_shares = {}
        block_hash_trees = {}
        share_hash_leaves = [None] * len(shares)
        for i in range(len(shares)):
            share_data = shares[i]
            shnum = share_ids[i]
            all_shares[shnum] = share_data

            # build the block hash tree. SDMF has only one leaf.
            leaves = [hashutil.block_hash(share_data)]
            t = hashtree.HashTree(leaves)
            block_hash_trees[shnum] = block_hash_tree = list(t)
            share_hash_leaves[shnum] = t[0]
        for leaf in share_hash_leaves:
            assert leaf is not None
        share_hash_tree = hashtree.HashTree(share_hash_leaves)
        share_hash_chain = {}
        for shnum in range(total_shares):
            needed_hashes = share_hash_tree.needed_hashes(shnum)
            share_hash_chain[shnum] = dict( [ (i, share_hash_tree[i])
                                              for i in needed_hashes ] )
        root_hash = share_hash_tree[0]
        assert len(root_hash) == 32

        prefix = self._pack_prefix(seqnum, root_hash,
                                   required_shares, total_shares,
                                   segment_size, data_length)

        # now pack the beginning of the share. All shares are the same up
        # to the signature, then they have divergent share hash chains,
        # then completely different block hash trees + IV + share data,
        # then they all share the same encprivkey at the end. The sizes
        # of everything are the same for all shares.

        signature = privkey.sign(prefix)

        verification_key = pubkey.serialize()

        final_shares = {}
        for shnum in range(total_shares):
            shc = share_hash_chain[shnum]
            share_hash_chain_s = "".join([struct.pack(">H32s", i, shc[i])
                                          for i in sorted(shc.keys())])
            bht = block_hash_trees[shnum]
            for h in bht:
                assert len(h) == 32
            block_hash_tree_s = "".join(bht)
            share_data = all_shares[shnum]
            offsets = self._pack_offsets(len(verification_key),
                                         len(signature),
                                         len(share_hash_chain_s),
                                         len(block_hash_tree_s),
                                         len(IV),
                                         len(share_data),
                                         len(encprivkey))

            final_shares[shnum] = "".join([prefix,
                                           offsets,
                                           verification_key,
                                           signature,
                                           share_hash_chain_s,
                                           block_hash_tree_s,
                                           IV,
                                           share_data,
                                           encprivkey])
        return (seqnum, root_hash, final_shares)


    def _pack_prefix(self, seqnum, root_hash,
                     required_shares, total_shares,
                     segment_size, data_length):
        prefix = struct.pack(">BQ32s" + "BBQQ",
                             0, # version,
                             seqnum,
                             root_hash,

                             required_shares,
                             total_shares,
                             segment_size,
                             data_length,
                             )
        return prefix

    def _pack_offsets(self, verification_key_length, signature_length,
                      share_hash_chain_length, block_hash_tree_length,
                      IV_length, share_data_length, encprivkey_length):
        post_offset = HEADER_LENGTH
        offsets = {}
        o1 = offsets['signature'] = post_offset + verification_key_length
        o2 = offsets['share_hash_chain'] = o1 + signature_length
        o3 = offsets['block_hash_tree'] = o2 + share_hash_chain_length
        assert IV_length == 16
        o4 = offsets['IV'] = o3 + block_hash_tree_length
        o5 = offsets['share_data'] = o4 + IV_length
        o6 = offsets['enc_privkey'] = o5 + share_data_length
        o7 = offsets['EOF'] = o6 + encprivkey_length

        return struct.pack(">LLLLLQQ",
                           offsets['signature'],
                           offsets['share_hash_chain'],
                           offsets['block_hash_tree'],
                           offsets['IV'],
                           offsets['share_data'],
                           offsets['enc_privkey'],
                           offsets['EOF'])

