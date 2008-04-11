

import os, struct, time
from itertools import count
from zope.interface import implements
from twisted.internet import defer
from allmydata.interfaces import IPublishStatus
from allmydata.util import base32, hashutil, mathutil, idlib, log
from allmydata import hashtree, codec, storage
from pycryptopp.cipher.aes import AES

from common import MODE_WRITE, UncoordinatedWriteError, DictOfSets
from servermap import ServerMap
from layout import pack_prefix, pack_share, unpack_header, pack_checkstring, \
     unpack_checkstring, SIGNED_PREFIX

class PublishStatus:
    implements(IPublishStatus)
    statusid_counter = count(0)
    def __init__(self):
        self.timings = {}
        self.timings["per_server"] = {}
        self.privkey_from = None
        self.peers_queried = None
        self.sharemap = None # DictOfSets
        self.problems = {}
        self.active = True
        self.storage_index = None
        self.helper = False
        self.encoding = ("?", "?")
        self.initial_read_size = None
        self.size = None
        self.status = "Not started"
        self.progress = 0.0
        self.counter = self.statusid_counter.next()
        self.started = time.time()

    def add_per_server_time(self, peerid, op, elapsed):
        assert op in ("read", "write")
        if peerid not in self.timings["per_server"]:
            self.timings["per_server"][peerid] = []
        self.timings["per_server"][peerid].append((op,elapsed))

    def get_started(self):
        return self.started
    def get_storage_index(self):
        return self.storage_index
    def get_encoding(self):
        return self.encoding
    def using_helper(self):
        return self.helper
    def get_size(self):
        return self.size
    def get_status(self):
        return self.status
    def get_progress(self):
        return self.progress
    def get_active(self):
        return self.active
    def get_counter(self):
        return self.counter

    def set_storage_index(self, si):
        self.storage_index = si
    def set_helper(self, helper):
        self.helper = helper
    def set_encoding(self, k, n):
        self.encoding = (k, n)
    def set_size(self, size):
        self.size = size
    def set_status(self, status):
        self.status = status
    def set_progress(self, value):
        self.progress = value
    def set_active(self, value):
        self.active = value

class Publish:
    """I represent a single act of publishing the mutable file to the grid. I
    will only publish my data if the servermap I am using still represents
    the current state of the world.

    To make the initial publish, set servermap to None.
    """

    # we limit the segment size as usual to constrain our memory footprint.
    # The max segsize is higher for mutable files, because we want to support
    # dirnodes with up to 10k children, and each child uses about 330 bytes.
    # If you actually put that much into a directory you'll be using a
    # footprint of around 14MB, which is higher than we'd like, but it is
    # more important right now to support large directories than to make
    # memory usage small when you use them. Once we implement MDMF (with
    # multiple segments), we will drop this back down, probably to 128KiB.
    MAX_SEGMENT_SIZE = 3500000

    def __init__(self, filenode, servermap):
        self._node = filenode
        self._servermap = servermap
        self._storage_index = self._node.get_storage_index()
        self._log_prefix = prefix = storage.si_b2a(self._storage_index)[:5]
        num = self._node._client.log("Publish(%s): starting" % prefix)
        self._log_number = num
        self._running = True

    def log(self, *args, **kwargs):
        if 'parent' not in kwargs:
            kwargs['parent'] = self._log_number
        return log.msg(*args, **kwargs)

    def log_err(self, *args, **kwargs):
        if 'parent' not in kwargs:
            kwargs['parent'] = self._log_number
        return log.err(*args, **kwargs)

    def publish(self, newdata):
        """Publish the filenode's current contents.  Returns a Deferred that
        fires (with None) when the publish has done as much work as it's ever
        going to do, or errbacks with ConsistencyError if it detects a
        simultaneous write.
        """

        # 1: generate shares (SDMF: files are small, so we can do it in RAM)
        # 2: perform peer selection, get candidate servers
        #  2a: send queries to n+epsilon servers, to determine current shares
        #  2b: based upon responses, create target map
        # 3: send slot_testv_and_readv_and_writev messages
        # 4: as responses return, update share-dispatch table
        # 4a: may need to run recovery algorithm
        # 5: when enough responses are back, we're done

        self.log("starting publish, datalen is %s" % len(newdata))

        self.done_deferred = defer.Deferred()

        self._writekey = self._node.get_writekey()
        assert self._writekey, "need write capability to publish"

        # first, which servers will we publish to? We require that the
        # servermap was updated in MODE_WRITE, so we can depend upon the
        # peerlist computed by that process instead of computing our own.
        if self._servermap:
            assert self._servermap.last_update_mode == MODE_WRITE
            # we will push a version that is one larger than anything present
            # in the grid, according to the servermap.
            self._new_seqnum = self._servermap.highest_seqnum() + 1
        else:
            # If we don't have a servermap, that's because we're doing the
            # initial publish
            self._new_seqnum = 1
            self._servermap = ServerMap()

        self.log(format="new seqnum will be %(seqnum)d",
                 seqnum=self._new_seqnum, level=log.NOISY)

        # having an up-to-date servermap (or using a filenode that was just
        # created for the first time) also guarantees that the following
        # fields are available
        self.readkey = self._node.get_readkey()
        self.required_shares = self._node.get_required_shares()
        assert self.required_shares is not None
        self.total_shares = self._node.get_total_shares()
        assert self.total_shares is not None
        self._pubkey = self._node.get_pubkey()
        assert self._pubkey
        self._privkey = self._node.get_privkey()
        assert self._privkey
        self._encprivkey = self._node.get_encprivkey()

        client = self._node._client
        full_peerlist = client.get_permuted_peers("storage",
                                                  self._storage_index)
        self.full_peerlist = full_peerlist # for use later, immutable
        self.bad_peers = set() # peerids who have errbacked/refused requests

        self.newdata = newdata
        self.salt = os.urandom(16)

        self.setup_encoding_parameters()

        self.surprised = False

        # we keep track of three tables. The first is our goal: which share
        # we want to see on which servers. This is initially populated by the
        # existing servermap.
        self.goal = set() # pairs of (peerid, shnum) tuples

        # the second table is our list of outstanding queries: those which
        # are in flight and may or may not be delivered, accepted, or
        # acknowledged. Items are added to this table when the request is
        # sent, and removed when the response returns (or errbacks).
        self.outstanding = set() # (peerid, shnum) tuples

        # the third is a table of successes: share which have actually been
        # placed. These are populated when responses come back with success.
        # When self.placed == self.goal, we're done.
        self.placed = set() # (peerid, shnum) tuples

        # we also keep a mapping from peerid to RemoteReference. Each time we
        # pull a connection out of the full peerlist, we add it to this for
        # use later.
        self.connections = {}

        # we use the servermap to populate the initial goal: this way we will
        # try to update each existing share in place.
        for (peerid, shares) in self._servermap.servermap.items():
            for (shnum, versionid, timestamp) in shares:
                self.goal.add( (peerid, shnum) )
                self.connections[peerid] = self._servermap.connections[peerid]

        # create the shares. We'll discard these as they are delivered. SMDF:
        # we're allowed to hold everything in memory.

        d = self._encrypt_and_encode()
        d.addCallback(self._generate_shares)
        d.addCallback(self.loop) # trigger delivery
        d.addErrback(self._fatal_error)

        return self.done_deferred

    def setup_encoding_parameters(self):
        segment_size = min(self.MAX_SEGMENT_SIZE, len(self.newdata))
        # this must be a multiple of self.required_shares
        segment_size = mathutil.next_multiple(segment_size,
                                              self.required_shares)
        self.segment_size = segment_size
        if segment_size:
            self.num_segments = mathutil.div_ceil(len(self.newdata),
                                                  segment_size)
        else:
            self.num_segments = 0
        assert self.num_segments in [0, 1,] # SDMF restrictions

    def _fatal_error(self, f):
        self.log("error during loop", failure=f, level=log.SCARY)
        self._done(f)

    def loop(self, ignored=None):
        self.log("entering loop", level=log.NOISY)
        self.update_goal()
        # how far are we from our goal?
        needed = self.goal - self.placed - self.outstanding

        if needed:
            # we need to send out new shares
            self.log(format="need to send %(needed)d new shares",
                     needed=len(needed), level=log.NOISY)
            d = self._send_shares(needed)
            d.addCallback(self.loop)
            d.addErrback(self._fatal_error)
            return

        if self.outstanding:
            # queries are still pending, keep waiting
            self.log(format="%(outstanding)d queries still outstanding",
                     outstanding=len(self.outstanding),
                     level=log.NOISY)
            return

        # no queries outstanding, no placements needed: we're done
        self.log("no queries outstanding, no placements needed: done",
                 level=log.OPERATIONAL)
        return self._done(None)

    def log_goal(self, goal):
        logmsg = []
        for (peerid, shnum) in goal:
            logmsg.append("sh%d to [%s]" % (shnum,
                                            idlib.shortnodeid_b2a(peerid)))
        self.log("current goal: %s" % (", ".join(logmsg)), level=log.NOISY)
        self.log("we are planning to push new seqnum=#%d" % self._new_seqnum,
                 level=log.NOISY)

    def update_goal(self):
        # first, remove any bad peers from our goal
        self.goal = set([ (peerid, shnum)
                          for (peerid, shnum) in self.goal
                          if peerid not in self.bad_peers ])

        # find the homeless shares:
        homefull_shares = set([shnum for (peerid, shnum) in self.goal])
        homeless_shares = set(range(self.total_shares)) - homefull_shares
        homeless_shares = sorted(list(homeless_shares))
        # place them somewhere. We prefer unused servers at the beginning of
        # the available peer list.

        if not homeless_shares:
            return

        # if log.recording_noisy
        if False:
            self.log_goal(self.goal)

        # if an old share X is on a node, put the new share X there too.
        # TODO: 1: redistribute shares to achieve one-per-peer, by copying
        #       shares from existing peers to new (less-crowded) ones. The
        #       old shares must still be updated.
        # TODO: 2: move those shares instead of copying them, to reduce future
        #       update work

        # this is a bit CPU intensive but easy to analyze. We create a sort
        # order for each peerid. If the peerid is marked as bad, we don't
        # even put them in the list. Then we care about the number of shares
        # which have already been assigned to them. After that we care about
        # their permutation order.
        old_assignments = DictOfSets()
        for (peerid, shnum) in self.goal:
            old_assignments.add(peerid, shnum)

        peerlist = []
        for i, (peerid, ss) in enumerate(self.full_peerlist):
            entry = (len(old_assignments.get(peerid, [])), i, peerid, ss)
            peerlist.append(entry)
        peerlist.sort()

        new_assignments = []
        # we then index this peerlist with an integer, because we may have to
        # wrap. We update the goal as we go.
        i = 0
        for shnum in homeless_shares:
            (ignored1, ignored2, peerid, ss) = peerlist[i]
            self.goal.add( (peerid, shnum) )
            self.connections[peerid] = ss
            i += 1
            if i >= len(peerlist):
                i = 0



    def _encrypt_and_encode(self):
        # this returns a Deferred that fires with a list of (sharedata,
        # sharenum) tuples. TODO: cache the ciphertext, only produce the
        # shares that we care about.
        self.log("_encrypt_and_encode")

        #started = time.time()

        key = hashutil.ssk_readkey_data_hash(self.salt, self.readkey)
        enc = AES(key)
        crypttext = enc.process(self.newdata)
        assert len(crypttext) == len(self.newdata)

        #now = time.time()
        #self._status.timings["encrypt"] = now - started
        #started = now

        # now apply FEC

        fec = codec.CRSEncoder()
        fec.set_params(self.segment_size,
                       self.required_shares, self.total_shares)
        piece_size = fec.get_block_size()
        crypttext_pieces = [None] * self.required_shares
        for i in range(len(crypttext_pieces)):
            offset = i * piece_size
            piece = crypttext[offset:offset+piece_size]
            piece = piece + "\x00"*(piece_size - len(piece)) # padding
            crypttext_pieces[i] = piece
            assert len(piece) == piece_size

        d = fec.encode(crypttext_pieces)
        def _done_encoding(res):
            #elapsed = time.time() - started
            #self._status.timings["encode"] = elapsed
            return res
        d.addCallback(_done_encoding)
        return d

    def _generate_shares(self, shares_and_shareids):
        # this sets self.shares and self.root_hash
        self.log("_generate_shares")
        #started = time.time()

        # we should know these by now
        privkey = self._privkey
        encprivkey = self._encprivkey
        pubkey = self._pubkey

        (shares, share_ids) = shares_and_shareids

        assert len(shares) == len(share_ids)
        assert len(shares) == self.total_shares
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
        for shnum in range(self.total_shares):
            needed_hashes = share_hash_tree.needed_hashes(shnum)
            share_hash_chain[shnum] = dict( [ (i, share_hash_tree[i])
                                              for i in needed_hashes ] )
        root_hash = share_hash_tree[0]
        assert len(root_hash) == 32
        self.log("my new root_hash is %s" % base32.b2a(root_hash))

        prefix = pack_prefix(self._new_seqnum, root_hash, self.salt,
                             self.required_shares, self.total_shares,
                             self.segment_size, len(self.newdata))

        # now pack the beginning of the share. All shares are the same up
        # to the signature, then they have divergent share hash chains,
        # then completely different block hash trees + salt + share data,
        # then they all share the same encprivkey at the end. The sizes
        # of everything are the same for all shares.

        #sign_started = time.time()
        signature = privkey.sign(prefix)
        #self._status.timings["sign"] = time.time() - sign_started

        verification_key = pubkey.serialize()

        final_shares = {}
        for shnum in range(self.total_shares):
            final_share = pack_share(prefix,
                                     verification_key,
                                     signature,
                                     share_hash_chain[shnum],
                                     block_hash_trees[shnum],
                                     all_shares[shnum],
                                     encprivkey)
            final_shares[shnum] = final_share
        #elapsed = time.time() - started
        #self._status.timings["pack"] = elapsed
        self.shares = final_shares
        self.root_hash = root_hash

        # we also need to build up the version identifier for what we're
        # pushing. Extract the offsets from one of our shares.
        assert final_shares
        offsets = unpack_header(final_shares.values()[0])[-1]
        offsets_tuple = tuple( [(key,value) for key,value in offsets.items()] )
        verinfo = (self._new_seqnum, root_hash, self.salt,
                   self.segment_size, len(self.newdata),
                   self.required_shares, self.total_shares,
                   prefix, offsets_tuple)
        self.versioninfo = verinfo



    def _send_shares(self, needed):
        self.log("_send_shares")
        #started = time.time()

        # we're finally ready to send out our shares. If we encounter any
        # surprises here, it's because somebody else is writing at the same
        # time. (Note: in the future, when we remove the _query_peers() step
        # and instead speculate about [or remember] which shares are where,
        # surprises here are *not* indications of UncoordinatedWriteError,
        # and we'll need to respond to them more gracefully.)

        # needed is a set of (peerid, shnum) tuples. The first thing we do is
        # organize it by peerid.

        peermap = DictOfSets()
        for (peerid, shnum) in needed:
            peermap.add(peerid, shnum)

        # the next thing is to build up a bunch of test vectors. The
        # semantics of Publish are that we perform the operation if the world
        # hasn't changed since the ServerMap was constructed (more or less).
        # For every share we're trying to place, we create a test vector that
        # tests to see if the server*share still corresponds to the
        # map.

        all_tw_vectors = {} # maps peerid to tw_vectors
        sm = self._servermap.servermap

        for (peerid, shnum) in needed:
            testvs = []
            for (old_shnum, old_versionid, old_timestamp) in sm.get(peerid,[]):
                if old_shnum == shnum:
                    # an old version of that share already exists on the
                    # server, according to our servermap. We will create a
                    # request that attempts to replace it.
                    (old_seqnum, old_root_hash, old_salt, old_segsize,
                     old_datalength, old_k, old_N, old_prefix,
                     old_offsets_tuple) = old_versionid
                    old_checkstring = pack_checkstring(old_seqnum,
                                                       old_root_hash,
                                                       old_salt)
                    testv = (0, len(old_checkstring), "eq", old_checkstring)
                    testvs.append(testv)
                    break
            if not testvs:
                # add a testv that requires the share not exist
                #testv = (0, 1, 'eq', "")

                # Unfortunately, foolscap-0.2.5 has a bug in the way inbound
                # constraints are handled. If the same object is referenced
                # multiple times inside the arguments, foolscap emits a
                # 'reference' token instead of a distinct copy of the
                # argument. The bug is that these 'reference' tokens are not
                # accepted by the inbound constraint code. To work around
                # this, we need to prevent python from interning the
                # (constant) tuple, by creating a new copy of this vector
                # each time. This bug is fixed in later versions of foolscap.
                testv = tuple([0, 1, 'eq', ""])
                testvs.append(testv)

            # the write vector is simply the share
            writev = [(0, self.shares[shnum])]

            if peerid not in all_tw_vectors:
                all_tw_vectors[peerid] = {}
                # maps shnum to (testvs, writevs, new_length)
            assert shnum not in all_tw_vectors[peerid]

            all_tw_vectors[peerid][shnum] = (testvs, writev, None)

        # we read the checkstring back from each share, however we only use
        # it to detect whether there was a new share that we didn't know
        # about. The success or failure of the write will tell us whether
        # there was a collision or not. If there is a collision, the first
        # thing we'll do is update the servermap, which will find out what
        # happened. We could conceivably reduce a roundtrip by using the
        # readv checkstring to populate the servermap, but really we'd have
        # to read enough data to validate the signatures too, so it wouldn't
        # be an overall win.
        read_vector = [(0, struct.calcsize(SIGNED_PREFIX))]

        # ok, send the messages!
        started = time.time()
        dl = []
        for (peerid, tw_vectors) in all_tw_vectors.items():

            write_enabler = self._node.get_write_enabler(peerid)
            renew_secret = self._node.get_renewal_secret(peerid)
            cancel_secret = self._node.get_cancel_secret(peerid)
            secrets = (write_enabler, renew_secret, cancel_secret)
            shnums = tw_vectors.keys()

            d = self._do_testreadwrite(peerid, secrets,
                                       tw_vectors, read_vector)
            d.addCallbacks(self._got_write_answer, self._got_write_error,
                           callbackArgs=(peerid, shnums, started),
                           errbackArgs=(peerid, shnums, started))
            d.addErrback(self._fatal_error)
            dl.append(d)

        return defer.DeferredList(dl) # purely for testing

    def _do_testreadwrite(self, peerid, secrets,
                          tw_vectors, read_vector):
        storage_index = self._storage_index
        ss = self.connections[peerid]

        #print "SS[%s] is %s" % (idlib.shortnodeid_b2a(peerid), ss), ss.tracker.interfaceName
        d = ss.callRemote("slot_testv_and_readv_and_writev",
                          storage_index,
                          secrets,
                          tw_vectors,
                          read_vector)
        return d

    def _got_write_answer(self, answer, peerid, shnums, started):
        lp = self.log("_got_write_answer from %s" %
                      idlib.shortnodeid_b2a(peerid))
        for shnum in shnums:
            self.outstanding.discard( (peerid, shnum) )
        sm = self._servermap.servermap

        wrote, read_data = answer

        if not wrote:
            self.log("our testv failed, so the write did not happen",
                     parent=lp, level=log.WEIRD)
            self.surprised = True
            self.bad_peers.add(peerid) # don't ask them again
            # use the checkstring to add information to the log message
            for (shnum,readv) in read_data.items():
                checkstring = readv[0]
                (other_seqnum,
                 other_roothash,
                 other_salt) = unpack_checkstring(checkstring)
                expected_version = self._servermap.version_on_peer(peerid,
                                                                   shnum)
                (seqnum, root_hash, IV, segsize, datalength, k, N, prefix,
                 offsets_tuple) = expected_version
                self.log("somebody modified the share on us:"
                         " shnum=%d: I thought they had #%d:R=%s,"
                         " but testv reported #%d:R=%s" %
                         (shnum,
                          seqnum, base32.b2a(root_hash)[:4],
                          other_seqnum, base32.b2a(other_roothash)[:4]),
                         parent=lp, level=log.NOISY)
            # self.loop() will take care of finding new homes
            return

        for shnum in shnums:
            self.placed.add( (peerid, shnum) )
            # and update the servermap. We strip the old entry out..
            newset = set([ t
                           for t in sm.get(peerid, [])
                           if t[0] != shnum ])
            sm[peerid] = newset
            # and add a new one
            sm[peerid].add( (shnum, self.versioninfo, started) )

        surprise_shares = set(read_data.keys()) - set(shnums)
        if surprise_shares:
            self.log("they had shares %s that we didn't know about" %
                     (list(surprise_shares),),
                     parent=lp, level=log.WEIRD)
            self.surprised = True
            return

        # self.loop() will take care of checking to see if we're done
        return

    def _got_write_error(self, f, peerid, shnums, started):
        for shnum in shnums:
            self.outstanding.discard( (peerid, shnum) )
        self.bad_peers.add(peerid)
        self.log(format="error while writing shares %(shnums)s to peerid %(peerid)s",
                 shnums=list(shnums), peerid=idlib.shortnodeid_b2a(peerid),
                 failure=f,
                 level=log.UNUSUAL)
        # self.loop() will take care of checking to see if we're done
        return



    def _log_dispatch_map(self, dispatch_map):
        for shnum, places in dispatch_map.items():
            sent_to = [(idlib.shortnodeid_b2a(peerid),
                        seqnum,
                        base32.b2a(root_hash)[:4])
                       for (peerid,seqnum,root_hash) in places]
            self.log(" share %d sent to: %s" % (shnum, sent_to),
                     level=log.NOISY)

    def _maybe_recover(self, (surprised, dispatch_map)):
        self.log("_maybe_recover, surprised=%s, dispatch_map:" % surprised,
                 level=log.NOISY)
        self._log_dispatch_map(dispatch_map)
        if not surprised:
            self.log(" no recovery needed")
            return
        self.log("We need recovery!", level=log.WEIRD)
        print "RECOVERY NOT YET IMPLEMENTED"
        # but dispatch_map will help us do it
        raise UncoordinatedWriteError("I was surprised!")

    def _done(self, res):
        if not self._running:
            return
        self._running = False
        #now = time.time()
        #self._status.timings["total"] = now - self._started
        #self._status.set_active(False)
        #self._status.set_status("Done")
        #self._status.set_progress(1.0)
        self.done_deferred.callback(res)
        return None

    def get_status(self):
        return self._status


