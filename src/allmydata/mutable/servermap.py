
import sys, time
from twisted.internet import defer
from twisted.python import failure
from foolscap.eventual import eventually
from allmydata.util import base32, hashutil, idlib, log
from allmydata import storage
from pycryptopp.publickey import rsa

from common import MODE_CHECK, MODE_ANYTHING, MODE_WRITE, MODE_ENOUGH, \
     DictOfSets, CorruptShareError, NeedMoreDataError
from layout import unpack_prefix_and_signature, unpack_header, unpack_share

class ServerMap:
    """I record the placement of mutable shares.

    This object records which shares (of various versions) are located on
    which servers.

    One purpose I serve is to inform callers about which versions of the
    mutable file are recoverable and 'current'.

    A second purpose is to serve as a state marker for test-and-set
    operations. I am passed out of retrieval operations and back into publish
    operations, which means 'publish this new version, but only if nothing
    has changed since I last retrieved this data'. This reduces the chances
    of clobbering a simultaneous (uncoordinated) write.

    @ivar servermap: a dictionary, mapping a (peerid, shnum) tuple to a
                     (versionid, timestamp) tuple. Each 'versionid' is a
                     tuple of (seqnum, root_hash, IV, segsize, datalength,
                     k, N, signed_prefix, offsets)

    @ivar connections: maps peerid to a RemoteReference

    @ivar bad_shares: a sequence of (peerid, shnum) tuples, describing
                      shares that I should ignore (because a previous user of
                      the servermap determined that they were invalid). The
                      updater only locates a certain number of shares: if
                      some of these turn out to have integrity problems and
                      are unusable, the caller will need to mark those shares
                      as bad, then re-update the servermap, then try again.
    """

    def __init__(self):
        self.servermap = {}
        self.connections = {}
        self.unreachable_peers = set() # peerids that didn't respond to queries
        self.problems = [] # mostly for debugging
        self.bad_shares = set()
        self.last_update_mode = None
        self.last_update_time = 0

    def mark_bad_share(self, peerid, shnum):
        """This share was found to be bad, not in the checkstring or
        signature, but deeper in the share, detected at retrieve time. Remove
        it from our list of useful shares, and remember that it is bad so we
        don't add it back again later.
        """
        key = (peerid, shnum)
        self.bad_shares.add(key)
        self.servermap.pop(key, None)

    def add_new_share(self, peerid, shnum, verinfo, timestamp):
        """We've written a new share out, replacing any that was there
        before."""
        key = (peerid, shnum)
        self.bad_shares.discard(key)
        self.servermap[key] = (verinfo, timestamp)

    def dump(self, out=sys.stdout):
        print >>out, "servermap:"

        for ( (peerid, shnum), (verinfo, timestamp) ) in self.servermap.items():
            (seqnum, root_hash, IV, segsize, datalength, k, N, prefix,
             offsets_tuple) = verinfo
            print >>out, ("[%s]: sh#%d seq%d-%s %d-of-%d len%d" %
                          (idlib.shortnodeid_b2a(peerid), shnum,
                           seqnum, base32.b2a(root_hash)[:4], k, N,
                           datalength))
        return out

    def all_peers(self):
        return set([peerid
                    for (peerid, shnum)
                    in self.servermap])

    def make_versionmap(self):
        """Return a dict that maps versionid to sets of (shnum, peerid,
        timestamp) tuples."""
        versionmap = DictOfSets()
        for ( (peerid, shnum), (verinfo, timestamp) ) in self.servermap.items():
            versionmap.add(verinfo, (shnum, peerid, timestamp))
        return versionmap

    def shares_on_peer(self, peerid):
        return set([shnum
                    for (s_peerid, shnum)
                    in self.servermap
                    if s_peerid == peerid])

    def version_on_peer(self, peerid, shnum):
        key = (peerid, shnum)
        if key in self.servermap:
            (verinfo, timestamp) = self.servermap[key]
            return verinfo
        return None
        return None

    def shares_available(self):
        """Return a dict that maps verinfo to tuples of
        (num_distinct_shares, k) tuples."""
        versionmap = self.make_versionmap()
        all_shares = {}
        for verinfo, shares in versionmap.items():
            s = set()
            for (shnum, peerid, timestamp) in shares:
                s.add(shnum)
            (seqnum, root_hash, IV, segsize, datalength, k, N, prefix,
             offsets_tuple) = verinfo
            all_shares[verinfo] = (len(s), k)
        return all_shares

    def highest_seqnum(self):
        available = self.shares_available()
        seqnums = [verinfo[0]
                   for verinfo in available.keys()]
        seqnums.append(0)
        return max(seqnums)

    def recoverable_versions(self):
        """Return a set of versionids, one for each version that is currently
        recoverable."""
        versionmap = self.make_versionmap()

        recoverable_versions = set()
        for (verinfo, shares) in versionmap.items():
            (seqnum, root_hash, IV, segsize, datalength, k, N, prefix,
             offsets_tuple) = verinfo
            shnums = set([shnum for (shnum, peerid, timestamp) in shares])
            if len(shnums) >= k:
                # this one is recoverable
                recoverable_versions.add(verinfo)

        return recoverable_versions

    def unrecoverable_versions(self):
        """Return a set of versionids, one for each version that is currently
        unrecoverable."""
        versionmap = self.make_versionmap()

        unrecoverable_versions = set()
        for (verinfo, shares) in versionmap.items():
            (seqnum, root_hash, IV, segsize, datalength, k, N, prefix,
             offsets_tuple) = verinfo
            shnums = set([shnum for (shnum, peerid, timestamp) in shares])
            if len(shnums) < k:
                unrecoverable_versions.add(verinfo)

        return unrecoverable_versions

    def best_recoverable_version(self):
        """Return a single versionid, for the so-called 'best' recoverable
        version. Sequence number is the primary sort criteria, followed by
        root hash. Returns None if there are no recoverable versions."""
        recoverable = list(self.recoverable_versions())
        recoverable.sort()
        if recoverable:
            return recoverable[-1]
        return None

    def unrecoverable_newer_versions(self):
        # Return a dict of versionid -> health, for versions that are
        # unrecoverable and have later seqnums than any recoverable versions.
        # These indicate that a write will lose data.
        pass

    def needs_merge(self):
        # return True if there are multiple recoverable versions with the
        # same seqnum, meaning that MutableFileNode.read_best_version is not
        # giving you the whole story, and that using its data to do a
        # subsequent publish will lose information.
        pass

class ServermapUpdater:
    def __init__(self, filenode, servermap, mode=MODE_ENOUGH):
        """I update a servermap, locating a sufficient number of useful
        shares and remembering where they are located.

        """

        self._node = filenode
        self._servermap = servermap
        self.mode = mode
        self._running = True

        self._storage_index = filenode.get_storage_index()
        self._last_failure = None

        # how much data should we read?
        #  * if we only need the checkstring, then [0:75]
        #  * if we need to validate the checkstring sig, then [543ish:799ish]
        #  * if we need the verification key, then [107:436ish]
        #   * the offset table at [75:107] tells us about the 'ish'
        #  * if we need the encrypted private key, we want [-1216ish:]
        #   * but we can't read from negative offsets
        #   * the offset table tells us the 'ish', also the positive offset
        # A future version of the SMDF slot format should consider using
        # fixed-size slots so we can retrieve less data. For now, we'll just
        # read 2000 bytes, which also happens to read enough actual data to
        # pre-fetch a 9-entry dirnode.
        self._read_size = 2000
        if mode == MODE_CHECK:
            # we use unpack_prefix_and_signature, so we need 1k
            self._read_size = 1000
        self._need_privkey = False
        if mode == MODE_WRITE and not self._node._privkey:
            self._need_privkey = True

        prefix = storage.si_b2a(self._storage_index)[:5]
        self._log_number = log.msg("SharemapUpdater(%s): starting" % prefix)

    def log(self, *args, **kwargs):
        if "parent" not in kwargs:
            kwargs["parent"] = self._log_number
        return log.msg(*args, **kwargs)

    def update(self):
        """Update the servermap to reflect current conditions. Returns a
        Deferred that fires with the servermap once the update has finished."""

        # self._valid_versions is a set of validated verinfo tuples. We just
        # use it to remember which versions had valid signatures, so we can
        # avoid re-checking the signatures for each share.
        self._valid_versions = set()

        # self.versionmap maps verinfo tuples to sets of (shnum, peerid,
        # timestamp) tuples. This is used to figure out which versions might
        # be retrievable, and to make the eventual data download faster.
        self.versionmap = DictOfSets()

        self._started = time.time()
        self._done_deferred = defer.Deferred()

        # first, which peers should be talk to? Any that were in our old
        # servermap, plus "enough" others.

        self._queries_completed = 0

        client = self._node._client
        full_peerlist = client.get_permuted_peers("storage",
                                                  self._node._storage_index)
        self.full_peerlist = full_peerlist # for use later, immutable
        self.extra_peers = full_peerlist[:] # peers are removed as we use them
        self._good_peers = set() # peers who had some shares
        self._empty_peers = set() # peers who don't have any shares
        self._bad_peers = set() # peers to whom our queries failed

        k = self._node.get_required_shares()
        if k is None:
            # make a guess
            k = 3
        N = self._node.get_required_shares()
        if N is None:
            N = 10
        self.EPSILON = k
        # we want to send queries to at least this many peers (although we
        # might not wait for all of their answers to come back)
        self.num_peers_to_query = k + self.EPSILON

        if self.mode == MODE_CHECK:
            initial_peers_to_query = dict(full_peerlist)
            must_query = set(initial_peers_to_query.keys())
            self.extra_peers = []
        elif self.mode == MODE_WRITE:
            # we're planning to replace all the shares, so we want a good
            # chance of finding them all. We will keep searching until we've
            # seen epsilon that don't have a share.
            self.num_peers_to_query = N + self.EPSILON
            initial_peers_to_query, must_query = self._build_initial_querylist()
            self.required_num_empty_peers = self.EPSILON

            # TODO: arrange to read lots of data from k-ish servers, to avoid
            # the extra round trip required to read large directories. This
            # might also avoid the round trip required to read the encrypted
            # private key.

        else:
            initial_peers_to_query, must_query = self._build_initial_querylist()

        # this is a set of peers that we are required to get responses from:
        # they are peers who used to have a share, so we need to know where
        # they currently stand, even if that means we have to wait for a
        # silently-lost TCP connection to time out. We remove peers from this
        # set as we get responses.
        self._must_query = must_query

        # now initial_peers_to_query contains the peers that we should ask,
        # self.must_query contains the peers that we must have heard from
        # before we can consider ourselves finished, and self.extra_peers
        # contains the overflow (peers that we should tap if we don't get
        # enough responses)

        self._send_initial_requests(initial_peers_to_query)
        return self._done_deferred

    def _build_initial_querylist(self):
        initial_peers_to_query = {}
        must_query = set()
        for peerid in self._servermap.all_peers():
            ss = self._servermap.connections[peerid]
            # we send queries to everyone who was already in the sharemap
            initial_peers_to_query[peerid] = ss
            # and we must wait for responses from them
            must_query.add(peerid)

        while ((self.num_peers_to_query > len(initial_peers_to_query))
               and self.extra_peers):
            (peerid, ss) = self.extra_peers.pop(0)
            initial_peers_to_query[peerid] = ss

        return initial_peers_to_query, must_query

    def _send_initial_requests(self, peerlist):
        self._queries_outstanding = set()
        self._sharemap = DictOfSets() # shnum -> [(peerid, seqnum, R)..]
        dl = []
        for (peerid, ss) in peerlist.items():
            self._queries_outstanding.add(peerid)
            self._do_query(ss, peerid, self._storage_index, self._read_size)

        # control flow beyond this point: state machine. Receiving responses
        # from queries is the input. We might send out more queries, or we
        # might produce a result.
        return None

    def _do_query(self, ss, peerid, storage_index, readsize):
        self.log(format="sending query to [%(peerid)s], readsize=%(readsize)d",
                 peerid=idlib.shortnodeid_b2a(peerid),
                 readsize=readsize,
                 level=log.NOISY)
        self._servermap.connections[peerid] = ss
        started = time.time()
        self._queries_outstanding.add(peerid)
        d = self._do_read(ss, peerid, storage_index, [], [(0, readsize)])
        d.addCallback(self._got_results, peerid, readsize, (ss, storage_index),
                      started)
        d.addErrback(self._query_failed, peerid)
        # errors that aren't handled by _query_failed (and errors caused by
        # _query_failed) get logged, but we still want to check for doneness.
        d.addErrback(log.err)
        d.addBoth(self._check_for_done)
        d.addErrback(self._fatal_error)
        return d

    def _do_read(self, ss, peerid, storage_index, shnums, readv):
        d = ss.callRemote("slot_readv", storage_index, shnums, readv)
        return d

    def _got_results(self, datavs, peerid, readsize, stuff, started):
        lp = self.log(format="got result from [%(peerid)s], %(numshares)d shares",
                     peerid=idlib.shortnodeid_b2a(peerid),
                     numshares=len(datavs),
                     level=log.NOISY)
        self._queries_outstanding.discard(peerid)
        self._must_query.discard(peerid)
        self._queries_completed += 1
        if not self._running:
            self.log("but we're not running, so we'll ignore it", parent=lp)
            return

        if datavs:
            self._good_peers.add(peerid)
        else:
            self._empty_peers.add(peerid)

        last_verinfo = None
        last_shnum = None
        for shnum,datav in datavs.items():
            data = datav[0]
            try:
                verinfo = self._got_results_one_share(shnum, data, peerid)
                last_verinfo = verinfo
                last_shnum = shnum
            except CorruptShareError, e:
                # log it and give the other shares a chance to be processed
                f = failure.Failure()
                self.log("bad share: %s %s" % (f, f.value),
                         parent=lp, level=log.WEIRD)
                self._bad_peers.add(peerid)
                self._last_failure = f
                self._servermap.problems.append(f)
                pass

        if self._need_privkey and last_verinfo:
            # send them a request for the privkey. We send one request per
            # server.
            (seqnum, root_hash, IV, segsize, datalength, k, N, prefix,
             offsets_tuple) = last_verinfo
            o = dict(offsets_tuple)

            self._queries_outstanding.add(peerid)
            readv = [ (o['enc_privkey'], (o['EOF'] - o['enc_privkey'])) ]
            ss = self._servermap.connections[peerid]
            d = self._do_read(ss, peerid, self._storage_index,
                              [last_shnum], readv)
            d.addCallback(self._got_privkey_results, peerid, last_shnum)
            d.addErrback(self._privkey_query_failed, peerid, last_shnum)
            d.addErrback(log.err)
            d.addCallback(self._check_for_done)
            d.addErrback(self._fatal_error)

        # all done!
        self.log("_got_results done", parent=lp)

    def _got_results_one_share(self, shnum, data, peerid):
        lp = self.log(format="_got_results: got shnum #%(shnum)d from peerid %(peerid)s",
                      shnum=shnum,
                      peerid=idlib.shortnodeid_b2a(peerid))

        # this might raise NeedMoreDataError, if the pubkey and signature
        # live at some weird offset. That shouldn't happen, so I'm going to
        # treat it as a bad share.
        (seqnum, root_hash, IV, k, N, segsize, datalength,
         pubkey_s, signature, prefix) = unpack_prefix_and_signature(data)

        if not self._node._pubkey:
            fingerprint = hashutil.ssk_pubkey_fingerprint_hash(pubkey_s)
            assert len(fingerprint) == 32
            if fingerprint != self._node._fingerprint:
                raise CorruptShareError(peerid, shnum,
                                        "pubkey doesn't match fingerprint")
            self._node._pubkey = self._deserialize_pubkey(pubkey_s)

        if self._need_privkey:
            self._try_to_extract_privkey(data, peerid, shnum)

        (ig_version, ig_seqnum, ig_root_hash, ig_IV, ig_k, ig_N,
         ig_segsize, ig_datalen, offsets) = unpack_header(data)
        offsets_tuple = tuple( [(key,value) for key,value in offsets.items()] )

        verinfo = (seqnum, root_hash, IV, segsize, datalength, k, N, prefix,
                   offsets_tuple)

        if verinfo not in self._valid_versions:
            # it's a new pair. Verify the signature.
            valid = self._node._pubkey.verify(prefix, signature)
            if not valid:
                raise CorruptShareError(peerid, shnum, "signature is invalid")

            # ok, it's a valid verinfo. Add it to the list of validated
            # versions.
            self.log(" found valid version %d-%s from %s-sh%d: %d-%d/%d/%d"
                     % (seqnum, base32.b2a(root_hash)[:4],
                        idlib.shortnodeid_b2a(peerid), shnum,
                        k, N, segsize, datalength),
                     parent=lp)
            self._valid_versions.add(verinfo)
        # We now know that this is a valid candidate verinfo.

        if (peerid, shnum) in self._servermap.bad_shares:
            # we've been told that the rest of the data in this share is
            # unusable, so don't add it to the servermap.
            self.log("but we've been told this is a bad share",
                     parent=lp, level=log.UNUSUAL)
            return verinfo

        # Add the info to our servermap.
        timestamp = time.time()
        self._servermap.add_new_share(peerid, shnum, verinfo, timestamp)
        # and the versionmap
        self.versionmap.add(verinfo, (shnum, peerid, timestamp))
        return verinfo

    def _deserialize_pubkey(self, pubkey_s):
        verifier = rsa.create_verifying_key_from_string(pubkey_s)
        return verifier

    def _try_to_extract_privkey(self, data, peerid, shnum):
        try:
            r = unpack_share(data)
        except NeedMoreDataError, e:
            # this share won't help us. oh well.
            offset = e.encprivkey_offset
            length = e.encprivkey_length
            self.log("shnum %d on peerid %s: share was too short (%dB) "
                     "to get the encprivkey; [%d:%d] ought to hold it" %
                     (shnum, idlib.shortnodeid_b2a(peerid), len(data),
                      offset, offset+length))
            # NOTE: if uncoordinated writes are taking place, someone might
            # change the share (and most probably move the encprivkey) before
            # we get a chance to do one of these reads and fetch it. This
            # will cause us to see a NotEnoughSharesError(unable to fetch
            # privkey) instead of an UncoordinatedWriteError . This is a
            # nuisance, but it will go away when we move to DSA-based mutable
            # files (since the privkey will be small enough to fit in the
            # write cap).

            return

        (seqnum, root_hash, IV, k, N, segsize, datalen,
         pubkey, signature, share_hash_chain, block_hash_tree,
         share_data, enc_privkey) = r

        return self._try_to_validate_privkey(self, enc_privkey, peerid, shnum)

    def _try_to_validate_privkey(self, enc_privkey, peerid, shnum):

        alleged_privkey_s = self._node._decrypt_privkey(enc_privkey)
        alleged_writekey = hashutil.ssk_writekey_hash(alleged_privkey_s)
        if alleged_writekey != self._node.get_writekey():
            self.log("invalid privkey from %s shnum %d" %
                     (idlib.nodeid_b2a(peerid)[:8], shnum), level=log.WEIRD)
            return

        # it's good
        self.log("got valid privkey from shnum %d on peerid %s" %
                 (shnum, idlib.shortnodeid_b2a(peerid)))
        privkey = rsa.create_signing_key_from_string(alleged_privkey_s)
        self._node._populate_encprivkey(enc_privkey)
        self._node._populate_privkey(privkey)
        self._need_privkey = False


    def _query_failed(self, f, peerid):
        self.log("error during query: %s %s" % (f, f.value), level=log.WEIRD)
        if not self._running:
            return
        self._must_query.discard(peerid)
        self._queries_outstanding.discard(peerid)
        self._bad_peers.add(peerid)
        self._servermap.problems.append(f)
        self._servermap.unreachable_peers.add(peerid) # TODO: overkill?
        self._queries_completed += 1
        self._last_failure = f

    def _got_privkey_results(self, datavs, peerid, shnum):
        self._queries_outstanding.discard(peerid)
        if not self._need_privkey:
            return
        if shnum not in datavs:
            self.log("privkey wasn't there when we asked it", level=log.WEIRD)
            return
        datav = datavs[shnum]
        enc_privkey = datav[0]
        self._try_to_validate_privkey(enc_privkey, peerid, shnum)

    def _privkey_query_failed(self, f, peerid, shnum):
        self._queries_outstanding.discard(peerid)
        self.log("error during privkey query: %s %s" % (f, f.value),
                 level=log.WEIRD)
        if not self._running:
            return
        self._queries_outstanding.discard(peerid)
        self._servermap.problems.append(f)
        self._last_failure = f

    def _check_for_done(self, res):
        # exit paths:
        #  return self._send_more_queries(outstanding) : send some more queries
        #  return self._done() : all done
        #  return : keep waiting, no new queries

        lp = self.log(format=("_check_for_done, mode is '%(mode)s', "
                              "%(outstanding)d queries outstanding, "
                              "%(extra)d extra peers available, "
                              "%(must)d 'must query' peers left"
                              ),
                      mode=self.mode,
                      outstanding=len(self._queries_outstanding),
                      extra=len(self.extra_peers),
                      must=len(self._must_query),
                      level=log.NOISY,
                      )

        if not self._running:
            self.log("but we're not running", parent=lp, level=log.NOISY)
            return

        if self._must_query:
            # we are still waiting for responses from peers that used to have
            # a share, so we must continue to wait. No additional queries are
            # required at this time.
            self.log("%d 'must query' peers left" % len(self._must_query),
                     parent=lp)
            return

        if (not self._queries_outstanding and not self.extra_peers):
            # all queries have retired, and we have no peers left to ask. No
            # more progress can be made, therefore we are done.
            self.log("all queries are retired, no extra peers: done",
                     parent=lp)
            return self._done()

        recoverable_versions = self._servermap.recoverable_versions()
        unrecoverable_versions = self._servermap.unrecoverable_versions()

        # what is our completion policy? how hard should we work?

        if self.mode == MODE_ANYTHING:
            if recoverable_versions:
                self.log("MODE_ANYTHING and %d recoverable versions: done"
                         % len(recoverable_versions),
                         parent=lp)
                return self._done()

        if self.mode == MODE_CHECK:
            # we used self._must_query, and we know there aren't any
            # responses still waiting, so that means we must be done
            self.log("MODE_CHECK: done",
                     parent=lp)
            return self._done()

        MAX_IN_FLIGHT = 5
        if self.mode == MODE_ENOUGH:
            # if we've queried k+epsilon servers, and we see a recoverable
            # version, and we haven't seen any unrecoverable higher-seqnum'ed
            # versions, then we're done.

            if self._queries_completed < self.num_peers_to_query:
                self.log(format="ENOUGH, %(completed)d completed, %(query)d to query: need more",
                         completed=self._queries_completed,
                         query=self.num_peers_to_query,
                         parent=lp)
                return self._send_more_queries(MAX_IN_FLIGHT)
            if not recoverable_versions:
                self.log("ENOUGH, no recoverable versions: need more",
                         parent=lp)
                return self._send_more_queries(MAX_IN_FLIGHT)
            highest_recoverable = max(recoverable_versions)
            highest_recoverable_seqnum = highest_recoverable[0]
            for unrec_verinfo in unrecoverable_versions:
                if unrec_verinfo[0] > highest_recoverable_seqnum:
                    # there is evidence of a higher-seqnum version, but we
                    # don't yet see enough shares to recover it. Try harder.
                    # TODO: consider sending more queries.
                    # TODO: consider limiting the search distance
                    self.log("ENOUGH, evidence of higher seqnum: need more")
                    return self._send_more_queries(MAX_IN_FLIGHT)
            # all the unrecoverable versions were old or concurrent with a
            # recoverable version. Good enough.
            self.log("ENOUGH: no higher-seqnum: done",
                     parent=lp)
            return self._done()

        if self.mode == MODE_WRITE:
            # we want to keep querying until we've seen a few that don't have
            # any shares, to be sufficiently confident that we've seen all
            # the shares. This is still less work than MODE_CHECK, which asks
            # every server in the world.

            if not recoverable_versions:
                self.log("WRITE, no recoverable versions: need more",
                         parent=lp)
                return self._send_more_queries(MAX_IN_FLIGHT)

            last_found = -1
            last_not_responded = -1
            num_not_responded = 0
            num_not_found = 0
            states = []
            found_boundary = False

            for i,(peerid,ss) in enumerate(self.full_peerlist):
                if peerid in self._bad_peers:
                    # query failed
                    states.append("x")
                    #self.log("loop [%s]: x" % idlib.shortnodeid_b2a(peerid))
                elif peerid in self._empty_peers:
                    # no shares
                    states.append("0")
                    #self.log("loop [%s]: 0" % idlib.shortnodeid_b2a(peerid))
                    if last_found != -1:
                        num_not_found += 1
                        if num_not_found >= self.EPSILON:
                            self.log("MODE_WRITE: found our boundary, %s" %
                                     "".join(states),
                                     parent=lp)
                            found_boundary = True
                            break

                elif peerid in self._good_peers:
                    # yes shares
                    states.append("1")
                    #self.log("loop [%s]: 1" % idlib.shortnodeid_b2a(peerid))
                    last_found = i
                    num_not_found = 0
                else:
                    # not responded yet
                    states.append("?")
                    #self.log("loop [%s]: ?" % idlib.shortnodeid_b2a(peerid))
                    last_not_responded = i
                    num_not_responded += 1

            if found_boundary:
                # we need to know that we've gotten answers from
                # everybody to the left of here
                if last_not_responded == -1:
                    # we're done
                    self.log("have all our answers",
                             parent=lp)
                    # .. unless we're still waiting on the privkey
                    if self._need_privkey:
                        self.log("but we're still waiting for the privkey",
                                 parent=lp)
                        # if we found the boundary but we haven't yet found
                        # the privkey, we may need to look further. If
                        # somehow all the privkeys were corrupted (but the
                        # shares were readable), then this is likely to do an
                        # exhaustive search.
                        return self._send_more_queries(MAX_IN_FLIGHT)
                    return self._done()
                # still waiting for somebody
                return self._send_more_queries(num_not_responded)

            # if we hit here, we didn't find our boundary, so we're still
            # waiting for peers
            self.log("MODE_WRITE: no boundary yet, %s" % "".join(states),
                     parent=lp)
            return self._send_more_queries(MAX_IN_FLIGHT)

        # otherwise, keep up to 5 queries in flight. TODO: this is pretty
        # arbitrary, really I want this to be something like k -
        # max(known_version_sharecounts) + some extra
        self.log("catchall: need more", parent=lp)
        return self._send_more_queries(MAX_IN_FLIGHT)

    def _send_more_queries(self, num_outstanding):
        more_queries = []

        while True:
            self.log(format=" there are %(outstanding)d queries outstanding",
                     outstanding=len(self._queries_outstanding),
                     level=log.NOISY)
            active_queries = len(self._queries_outstanding) + len(more_queries)
            if active_queries >= num_outstanding:
                break
            if not self.extra_peers:
                break
            more_queries.append(self.extra_peers.pop(0))

        self.log(format="sending %(more)d more queries: %(who)s",
                 more=len(more_queries),
                 who=" ".join(["[%s]" % idlib.shortnodeid_b2a(peerid)
                               for (peerid,ss) in more_queries]),
                 level=log.NOISY)

        for (peerid, ss) in more_queries:
            self._do_query(ss, peerid, self._storage_index, self._read_size)
            # we'll retrigger when those queries come back

    def _done(self):
        if not self._running:
            return
        self._running = False
        self._servermap.last_update_mode = self.mode
        self._servermap.last_update_time = self._started
        # the servermap will not be touched after this
        eventually(self._done_deferred.callback, self._servermap)

    def _fatal_error(self, f):
        self.log("fatal error", failure=f, level=log.WEIRD)
        self._done_deferred.errback(f)

