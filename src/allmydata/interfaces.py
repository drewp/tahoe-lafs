
from zope.interface import Interface
from foolscap.schema import StringConstraint, ListOf, TupleOf, SetOf, DictOf, \
     ChoiceOf
from foolscap import RemoteInterface, Referenceable

HASH_SIZE=32

Hash = StringConstraint(maxLength=HASH_SIZE,
                        minLength=HASH_SIZE)# binary format 32-byte SHA256 hash
Nodeid = StringConstraint(maxLength=20,
                          minLength=20) # binary format 20-byte SHA1 hash
FURL = StringConstraint(1000)
StorageIndex = StringConstraint(16)
URI = StringConstraint(300) # kind of arbitrary
DirnodeURI = StringConstraint(300, regexp=r'^URI:DIR(-RO)?:pb://[a-z0-9]+@[^/]+/[^:]+:[a-z0-9]+$')
MAX_BUCKETS = 200  # per peer

# MAX_SEGMENT_SIZE in encode.py is 1 MiB (this constraint allows k = 1)
ShareData = StringConstraint(2**20)
URIExtensionData = StringConstraint(1000)
LeaseRenewSecret = Hash # used to protect bucket lease renewal requests
LeaseCancelSecret = Hash # used to protect bucket lease cancellation requests


class RIIntroducerClient(RemoteInterface):
    def new_peers(furls=SetOf(FURL)):
        return None
    def set_encoding_parameters(parameters=(int, int, int)):
        """Advise the client of the recommended k-of-n encoding parameters
        for this grid. 'parameters' is a tuple of (k, desired, n), where 'n'
        is the total number of shares that will be created for any given
        file, while 'k' is the number of shares that must be retrieved to
        recover that file, and 'desired' is the minimum number of shares that
        must be placed before the uploader will consider its job a success.
        n/k is the expansion ratio, while k determines the robustness.

        Introducers should specify 'n' according to the expected size of the
        grid (there is no point to producing more shares than there are
        peers), and k according to the desired reliability-vs-overhead goals.

        Note that setting k=1 is equivalent to simple replication.
        """
        return None

class RIIntroducer(RemoteInterface):
    def hello(node=RIIntroducerClient, furl=FURL):
        return None

class RIClient(RemoteInterface):
    def get_versions():
        """Return a tuple of (my_version, oldest_supported) strings.

        Each string can be parsed by an allmydata.util.version.Version
        instance, and then compared. The first goal is to make sure that
        nodes are not confused by speaking to an incompatible peer. The
        second goal is to enable the development of backwards-compatibility
        code.

        This method is likely to change in incompatible ways until we get the
        whole compatibility scheme nailed down.
        """
        return TupleOf(str, str)
    def get_service(name=str):
        return Referenceable
    def get_nodeid():
        return Nodeid

class RIBucketWriter(RemoteInterface):
    def write(offset=int, data=ShareData):
        return None

    def close():
        """
        If the data that has been written is incomplete or inconsistent then
        the server will throw the data away, else it will store it for future
        retrieval.
        """
        return None

class RIBucketReader(RemoteInterface):
    def read(offset=int, length=int):
        return ShareData

TestVector = ListOf(TupleOf(int, int, str, str))
# elements are (offset, length, operator, specimen)
# operator is one of "lt, le, eq, ne, ge, gt, nop"
# nop always passes and is used to fetch data while writing.
# you should use length==len(specimen) for everything except nop
DataVector = ListOf(TupleOf(int, ShareData))
# (offset, data). This limits us to 30 writes of 1MiB each per call
TestResults = ListOf(str)
# returns data[offset:offset+length] for each element of TestVector

class RIMutableSlot(RemoteInterface):
    def testv_and_writev(write_enabler=Hash,
                         testv=TestVector,
                         datav=DataVector,
                         new_length=ChoiceOf(None, int)):
        """General-purpose test-and-set operation for mutable slots. Perform
        the given comparisons. If they all pass, then apply the write vector.

        If new_length is not None, use it to set the size of the container.
        This can be used to pre-allocate space for a series of upcoming
        writes, or truncate existing data. If the container is growing,
        new_length will be applied before datav. If the container is
        shrinking, it will be applied afterwards.

        Return the old data that was used for the comparisons.

        The boolean return value is True if the write vector was applied,
        false if not.

        If the write_enabler is wrong, this will raise BadWriterEnablerError.
        To enable share migration, the exception will have the nodeid used
        for the old write enabler embedded in it, in the following string::

         The write enabler was recorded by nodeid '%s'.

        """
        return TupleOf(bool, TestResults)

    def read(offset=int, length=int):
        return ShareData

    def get_length():
        return int

class RIStorageServer(RemoteInterface):
    def allocate_buckets(storage_index=StorageIndex,
                         renew_secret=LeaseRenewSecret,
                         cancel_secret=LeaseCancelSecret,
                         sharenums=SetOf(int, maxLength=MAX_BUCKETS),
                         allocated_size=int, canary=Referenceable):
        """
        @param storage_index: the index of the bucket to be created or
                              increfed.
        @param sharenums: these are the share numbers (probably between 0 and
                          99) that the sender is proposing to store on this
                          server.
        @param renew_secret: This is the secret used to protect bucket refresh
                             This secret is generated by the client and
                             stored for later comparison by the server. Each
                             server is given a different secret.
        @param cancel_secret: Like renew_secret, but protects bucket decref.
        @param canary: If the canary is lost before close(), the bucket is
                       deleted.
        @return: tuple of (alreadygot, allocated), where alreadygot is what we
                 already have and is what we hereby agree to accept. New
                 leases are added for shares in both lists.
        """
        return TupleOf(SetOf(int, maxLength=MAX_BUCKETS),
                       DictOf(int, RIBucketWriter, maxKeys=MAX_BUCKETS))

    def renew_lease(storage_index=StorageIndex, renew_secret=LeaseRenewSecret):
        """
        Renew the lease on a given bucket. Some networks will use this, some
        will not.
        """

    def cancel_lease(storage_index=StorageIndex,
                     cancel_secret=LeaseCancelSecret):
        """
        Cancel the lease on a given bucket. If this was the last lease on the
        bucket, the bucket will be deleted.
        """

    def get_buckets(storage_index=StorageIndex):
        return DictOf(int, RIBucketReader, maxKeys=MAX_BUCKETS)


    def allocate_mutable_slot(storage_index=StorageIndex,
                              write_enabler=Hash,
                              renew_secret=LeaseRenewSecret,
                              cancel_secret=LeaseCancelSecret,
                              sharenums=SetOf(int, maxLength=MAX_BUCKETS),
                              allocated_size=int):
        """
        @param storage_index: the index of the bucket to be created or
                              increfed.
        @param write_enabler: a secret that is stored along with the slot.
                              Writes are accepted from any caller who can
                              present the matching secret. A different secret
                              should be used for each slot*server pair.
        @param renew_secret: This is the secret used to protect bucket refresh
                             This secret is generated by the client and
                             stored for later comparison by the server. Each
                             server is given a different secret.
        @param cancel_secret: Like renew_secret, but protects bucket decref.
        @param sharenums: these are the share numbers (probably between 0 and
                          99) that the sender is proposing to store on this
                          server.
        @param allocated_size: all shares will pre-allocate this many bytes.
                               Use this to a) confirm that you can claim as
                               much space as you want before you actually
                               send the data, and b) reduce the disk-IO cost
                               of doing incremental writes.

        @return: dict mapping sharenum to slot. The return value may include
                 more sharenums than asked, if some shares already existed.
                 New leases are added for all
                 shares.

        """
        return DictOf(int, RIMutableSlot, maxKeys=MAX_BUCKETS)

    def get_mutable_slot(storage_index=StorageIndex):
        """This returns an empty dictionary if the server has no shares
        of the slot mentioned."""
        return DictOf(int, RIMutableSlot, maxKeys=MAX_BUCKETS)


class IStorageBucketWriter(Interface):
    def put_block(segmentnum=int, data=ShareData):
        """@param data: For most segments, this data will be 'blocksize'
        bytes in length. The last segment might be shorter.
        @return: a Deferred that fires (with None) when the operation completes
        """

    def put_plaintext_hashes(hashes=ListOf(Hash, maxLength=2**20)):
        """
        @return: a Deferred that fires (with None) when the operation completes
        """

    def put_crypttext_hashes(hashes=ListOf(Hash, maxLength=2**20)):
        """
        @return: a Deferred that fires (with None) when the operation completes
        """

    def put_block_hashes(blockhashes=ListOf(Hash, maxLength=2**20)):
        """
        @return: a Deferred that fires (with None) when the operation completes
        """
        
    def put_share_hashes(sharehashes=ListOf(TupleOf(int, Hash),
                                            maxLength=2**20)):
        """
        @return: a Deferred that fires (with None) when the operation completes
        """

    def put_uri_extension(data=URIExtensionData):
        """This block of data contains integrity-checking information (hashes
        of plaintext, crypttext, and shares), as well as encoding parameters
        that are necessary to recover the data. This is a serialized dict
        mapping strings to other strings. The hash of this data is kept in
        the URI and verified before any of the data is used. All buckets for
        a given file contain identical copies of this data.

        The serialization format is specified with the following pseudocode:
        for k in sorted(dict.keys()):
            assert re.match(r'^[a-zA-Z_\-]+$', k)
            write(k + ':' + netstring(dict[k]))

        @return: a Deferred that fires (with None) when the operation completes
        """

    def close():
        """Finish writing and close the bucket. The share is not finalized
        until this method is called: if the uploading client disconnects
        before calling close(), the partially-written share will be
        discarded.

        @return: a Deferred that fires (with None) when the operation completes
        """

class IStorageBucketReader(Interface):

    def get_block(blocknum=int):
        """Most blocks will be the same size. The last block might be shorter
        than the others.

        @return: ShareData
        """

    def get_plaintext_hashes():
        """
        @return: ListOf(Hash, maxLength=2**20)
        """

    def get_crypttext_hashes():
        """
        @return: ListOf(Hash, maxLength=2**20)
        """

    def get_block_hashes():
        """
        @return: ListOf(Hash, maxLength=2**20)
        """

    def get_share_hashes():
        """
        @return: ListOf(TupleOf(int, Hash), maxLength=2**20)
        """

    def get_uri_extension():
        """
        @return: URIExtensionData
        """



# hm, we need a solution for forward references in schemas
from foolscap.schema import Any
RIMutableDirectoryNode_ = Any() # TODO: how can we avoid this?

FileNode_ = Any() # TODO: foolscap needs constraints on copyables
DirectoryNode_ = Any() # TODO: same
AnyNode_ = ChoiceOf(FileNode_, DirectoryNode_)
EncryptedThing = str

class RIVirtualDriveServer(RemoteInterface):
    def get_public_root_uri():
        """Obtain the URI for this server's global publically-writable root
        directory. This returns a read-write directory URI.

        If this vdrive server does not offer a public root, this will
        raise an exception."""
        return DirnodeURI

    def create_directory(index=Hash, write_enabler=Hash):
        """Create a new (empty) directory, unattached to anything else.

        This returns the same index that was passed in.
        """
        return Hash

    def get(index=Hash, key=Hash):
        """Retrieve a named child of the given directory. 'index' specifies
        which directory is being accessed, and is generally the hash of the
        read key. 'key' is the hash of the read key and the child name.

        This operation returns a pair of encrypted strings. The first string
        is meant to be decrypted by the Write Key and provides read-write
        access to the child. If this directory holds read-only access to the
        child, this first string will be an empty string. The second string
        is meant to be decrypted by the Read Key and provides read-only
        access to the child.

        When the child is a read-write directory, the encrypted URI:DIR-RO
        will be in the read slot, and the encrypted URI:DIR will be in the
        write slot. When the child is a read-only directory, the encrypted
        URI:DIR-RO will be in the read slot and the write slot will be empty.
        When the child is a CHK file, the encrypted URI:CHK will be in the
        read slot, and the write slot will be empty.

        This might raise IndexError if there is no child by the desired name.
        """
        return (EncryptedThing, EncryptedThing)

    def list(index=Hash):
        """List the contents of a directory.

        This returns a list of (NAME, WRITE, READ) tuples. Each value is an
        encrypted string (although the WRITE value may sometimes be an empty
        string).

        NAME: the child name, encrypted with the Read Key
        WRITE: the child write URI, encrypted with the Write Key, or an
               empty string if this child is read-only
        READ: the child read URI, encrypted with the Read Key
        """
        return ListOf((EncryptedThing, EncryptedThing, EncryptedThing),
                      maxLength=1000,
                      )

    def set(index=Hash, write_enabler=Hash, key=Hash,
            name=EncryptedThing, write=EncryptedThing, read=EncryptedThing):
        """Set a child object. I will replace any existing child of the same
        name.
        """

    def delete(index=Hash, write_enabler=Hash, key=Hash):
        """Delete a specific child.

        This uses the hashed key to locate a specific child, and deletes it.
        """


class IURI(Interface):
    def init_from_string(uri):
        """Accept a string (as created by my to_string() method) and populate
        this instance with its data. I am not normally called directly,
        please use the module-level uri.from_string() function to convert
        arbitrary URI strings into IURI-providing instances."""

    def is_readonly():
        """Return False if this URI be used to modify the data. Return True
        if this URI cannot be used to modify the data."""

    def is_mutable():
        """Return True if the data can be modified by *somebody* (perhaps
        someone who has a more powerful URI than this one)."""

    def get_readonly():
        """Return another IURI instance, which represents a read-only form of
        this one. If is_readonly() is True, this returns self."""

    def get_verifier():
        """Return an instance that provides IVerifierURI, which can be used
        to check on the availability of the file or directory, without
        providing enough capabilities to actually read or modify the
        contents. This may return None if the file does not need checking or
        verification (e.g. LIT URIs).
        """

    def to_string():
        """Return a string of printable ASCII characters, suitable for
        passing into init_from_string."""

class IVerifierURI(Interface):
    def init_from_string(uri):
        """Accept a string (as created by my to_string() method) and populate
        this instance with its data. I am not normally called directly,
        please use the module-level uri.from_string() function to convert
        arbitrary URI strings into IURI-providing instances."""

    def to_string():
        """Return a string of printable ASCII characters, suitable for
        passing into init_from_string."""

class IDirnodeURI(Interface):
    """I am a URI which represents a dirnode."""


class IFileURI(Interface):
    """I am a URI which represents a filenode."""
    def get_size():
        """Return the length (in bytes) of the file that I represent."""


class IFileNode(Interface):
    def download(target):
        """Download the file's contents to a given IDownloadTarget"""
    def download_to_data():
        """Download the file's contents. Return a Deferred that fires
        with those contents."""

    def get_uri():
        """Return the URI that can be used by others to get access to this
        file.
        """
    def get_size():
        """Return the length (in bytes) of the data this node represents."""

    def get_verifier():
        """Return an IVerifierURI instance that represents the
        'verifiy/refresh capability' for this node. The holder of this
        capability will be able to renew the lease for this node, protecting
        it from garbage-collection. They will also be able to ask a server if
        it holds a share for the file or directory.
        """

    def check():
        """Perform a file check. See IChecker.check for details."""

class IDirectoryNode(Interface):
    def is_mutable():
        """Return True if this directory is mutable, False if it is read-only.
        """

    def get_uri():
        """Return the directory URI that can be used by others to get access
        to this directory node. If this node is read-only, the URI will only
        offer read-only access. If this node is read-write, the URI will
        offer read-write acess.

        If you have read-write access to a directory and wish to share merely
        read-only access with others, use get_immutable_uri().

        The dirnode ('1') URI returned by this method can be used in
        set_uri() on a different directory ('2') to 'mount' a reference to
        this directory ('1') under the other ('2'). This URI is just a
        string, so it can be passed around through email or other out-of-band
        protocol.
        """

    def get_immutable_uri():
        """Return the directory URI that can be used by others to get
        read-only access to this directory node. The result is a read-only
        URI, regardless of whether this dirnode is read-only or read-write.

        If you have merely read-only access to this dirnode,
        get_immutable_uri() will return the same thing as get_uri().
        """

    def get_verifier():
        """Return an IVerifierURI instance that represents the
        'verifiy/refresh capability' for this node. The holder of this
        capability will be able to renew the lease for this node, protecting
        it from garbage-collection. They will also be able to ask a server if
        it holds a share for the file or directory.
        """

    def check():
        """Perform a file check. See IChecker.check for details."""

    def list():
        """I return a Deferred that fires with a dictionary mapping child
        name to an IFileNode or IDirectoryNode."""

    def has_child(name):
        """I return a Deferred that fires with a boolean, True if there
        exists a child of the given name, False if not."""

    def get(name):
        """I return a Deferred that fires with a specific named child node,
        either an IFileNode or an IDirectoryNode."""

    def get_child_at_path(path):
        """Transform a child path into an IDirectoryNode or IFileNode.

        I perform a recursive series of 'get' operations to find the named
        descendant node. I return a Deferred that fires with the node, or
        errbacks with IndexError if the node could not be found.

        The path can be either a single string (slash-separated) or a list of
        path-name elements.
        """

    def set_uri(name, child_uri):
        """I add a child (by URI) at the specific name. I return a Deferred
        that fires when the operation finishes. I will replace any existing
        child of the same name.

        The child_uri could be for a file, or for a directory (either
        read-write or read-only, using a URI that came from get_uri() ).

        If this directory node is read-only, the Deferred will errback with a
        NotMutableError."""

    def set_node(name, child):
        """I add a child at the specific name. I return a Deferred that fires
        when the operation finishes. This Deferred will fire with the child
        node that was just added. I will replace any existing child of the
        same name.

        If this directory node is read-only, the Deferred will errback with a
        NotMutableError."""

    def add_file(name, uploadable):
        """I upload a file (using the given IUploadable), then attach the
        resulting FileNode to the directory at the given name. I return a
        Deferred that fires (with the IFileNode of the uploaded file) when
        the operation completes."""

    def delete(name):
        """I remove the child at the specific name. I return a Deferred that
        fires when the operation finishes."""

    def create_empty_directory(name):
        """I create and attach an empty directory at the given name. I return
        a Deferred that fires when the operation finishes."""

    def move_child_to(current_child_name, new_parent, new_child_name=None):
        """I take one of my children and move them to a new parent. The child
        is referenced by name. On the new parent, the child will live under
        'new_child_name', which defaults to 'current_child_name'. I return a
        Deferred that fires when the operation finishes."""

    def build_manifest():
        """Return a frozenset of verifier-capability strings for all nodes
        (directories and files) reachable from this one."""

class ICodecEncoder(Interface):
    def set_params(data_size, required_shares, max_shares):
        """Set up the parameters of this encoder.

        This prepares the encoder to perform an operation that converts a
        single block of data into a number of shares, such that a future
        ICodecDecoder can use a subset of these shares to recover the
        original data. This operation is invoked by calling encode(). Once
        the encoding parameters are set up, the encode operation can be
        invoked multiple times.

        set_params() prepares the encoder to accept blocks of input data that
        are exactly 'data_size' bytes in length. The encoder will be prepared
        to produce 'max_shares' shares for each encode() operation (although
        see the 'desired_share_ids' to use less CPU). The encoding math will
        be chosen such that the decoder can get by with as few as
        'required_shares' of these shares and still reproduce the original
        data. For example, set_params(1000, 5, 5) offers no redundancy at
        all, whereas set_params(1000, 1, 10) provides 10x redundancy.

        Numerical Restrictions: 'data_size' is required to be an integral
        multiple of 'required_shares'. In general, the caller should choose
        required_shares and max_shares based upon their reliability
        requirements and the number of peers available (the total storage
        space used is roughly equal to max_shares*data_size/required_shares),
        then choose data_size to achieve the memory footprint desired (larger
        data_size means more efficient operation, smaller data_size means
        smaller memory footprint).

        In addition, 'max_shares' must be equal to or greater than
        'required_shares'. Of course, setting them to be equal causes
        encode() to degenerate into a particularly slow form of the 'split'
        utility.

        See encode() for more details about how these parameters are used.

        set_params() must be called before any other ICodecEncoder methods
        may be invoked.
        """

    def get_encoder_type():
        """Return a short string that describes the type of this encoder.

        There is required to be a global table of encoder classes. This method
        returns an index into this table; the value at this index is an
        encoder class, and this encoder is an instance of that class.
        """

    def get_serialized_params(): # TODO: maybe, maybe not
        """Return a string that describes the parameters of this encoder.

        This string can be passed to the decoder to prepare it for handling
        the encoded shares we create. It might contain more information than
        was presented to set_params(), if there is some flexibility of
        parameter choice.

        This string is intended to be embedded in the URI, so there are
        several restrictions on its contents. At the moment I'm thinking that
        this means it may contain hex digits and hyphens, and nothing else.
        The idea is that the URI contains something like '%s:%s:%s' %
        (encoder.get_encoder_name(), encoder.get_serialized_params(),
        b2a(crypttext_hash)), and this is enough information to construct a
        compatible decoder.
        """

    def get_block_size():
        """Return the length of the shares that encode() will produce.
        """

    def encode_proposal(data, desired_share_ids=None):
        """Encode some data.

        'data' must be a string (or other buffer object), and len(data) must
        be equal to the 'data_size' value passed earlier to set_params().

        This will return a Deferred that will fire with two lists. The first
        is a list of shares, each of which is a string (or other buffer
        object) such that len(share) is the same as what get_share_size()
        returned earlier. The second is a list of shareids, in which each is
        an integer. The lengths of the two lists will always be equal to each
        other. The user should take care to keep each share closely
        associated with its shareid, as one is useless without the other.

        The length of this output list will normally be the same as the value
        provided to the 'max_shares' parameter of set_params(). This may be
        different if 'desired_share_ids' is provided.

        'desired_share_ids', if provided, is required to be a sequence of
        ints, each of which is required to be >= 0 and < max_shares. If not
        provided, encode() will produce 'max_shares' shares, as if
        'desired_share_ids' were set to range(max_shares). You might use this
        if you initially thought you were going to use 10 peers, started
        encoding, and then two of the peers dropped out: you could use
        desired_share_ids= to skip the work (both memory and CPU) of
        producing shares for the peers which are no longer available.

        """

    def encode(inshares, desired_share_ids=None):
        """Encode some data. This may be called multiple times. Each call is 
        independent.

        inshares is a sequence of length required_shares, containing buffers
        (i.e. strings), where each buffer contains the next contiguous
        non-overlapping segment of the input data. Each buffer is required to
        be the same length, and the sum of the lengths of the buffers is
        required to be exactly the data_size promised by set_params(). (This
        implies that the data has to be padded before being passed to
        encode(), unless of course it already happens to be an even multiple
        of required_shares in length.)

         ALSO: the requirement to break up your data into 'required_shares'
         chunks before calling encode() feels a bit surprising, at least from
         the point of view of a user who doesn't know how FEC works. It feels
         like an implementation detail that has leaked outside the
         abstraction barrier. Can you imagine a use case in which the data to
         be encoded might already be available in pre-segmented chunks, such
         that it is faster or less work to make encode() take a list rather
         than splitting a single string?

         ALSO ALSO: I think 'inshares' is a misleading term, since encode()
         is supposed to *produce* shares, so what it *accepts* should be
         something other than shares. Other places in this interface use the
         word 'data' for that-which-is-not-shares.. maybe we should use that
         term?

        'desired_share_ids', if provided, is required to be a sequence of
        ints, each of which is required to be >= 0 and < max_shares. If not
        provided, encode() will produce 'max_shares' shares, as if
        'desired_share_ids' were set to range(max_shares). You might use this
        if you initially thought you were going to use 10 peers, started
        encoding, and then two of the peers dropped out: you could use
        desired_share_ids= to skip the work (both memory and CPU) of
        producing shares for the peers which are no longer available.

        For each call, encode() will return a Deferred that fires with two
        lists, one containing shares and the other containing the shareids.
        The get_share_size() method can be used to determine the length of
        the share strings returned by encode(). Each shareid is a small
        integer, exactly as passed into 'desired_share_ids' (or
        range(max_shares), if desired_share_ids was not provided).

        The shares and their corresponding shareids are required to be kept 
        together during storage and retrieval. Specifically, the share data is 
        useless by itself: the decoder needs to be told which share is which 
        by providing it with both the shareid and the actual share data.

        This function will allocate an amount of memory roughly equal to::

         (max_shares - required_shares) * get_share_size()

        When combined with the memory that the caller must allocate to
        provide the input data, this leads to a memory footprint roughly
        equal to the size of the resulting encoded shares (i.e. the expansion
        factor times the size of the input segment).
        """

        # rejected ideas:
        #
        #  returning a list of (shareidN,shareN) tuples instead of a pair of
        #  lists (shareids..,shares..). Brian thought the tuples would
        #  encourage users to keep the share and shareid together throughout
        #  later processing, Zooko pointed out that the code to iterate
        #  through two lists is not really more complicated than using a list
        #  of tuples and there's also a performance improvement
        #
        #  having 'data_size' not required to be an integral multiple of
        #  'required_shares'. Doing this would require encode() to perform
        #  padding internally, and we'd prefer to have any padding be done
        #  explicitly by the caller. Yes, it is an abstraction leak, but
        #  hopefully not an onerous one.


class ICodecDecoder(Interface):
    def set_serialized_params(params):
        """Set up the parameters of this encoder, from a string returned by
        encoder.get_serialized_params()."""

    def get_needed_shares():
        """Return the number of shares needed to reconstruct the data.
        set_serialized_params() is required to be called before this."""

    def decode(some_shares, their_shareids):
        """Decode a partial list of shares into data.

        'some_shares' is required to be a sequence of buffers of sharedata, a
        subset of the shares returned by ICodecEncode.encode(). Each share is
        required to be of the same length.  The i'th element of their_shareids
        is required to be the shareid of the i'th buffer in some_shares.

        This returns a Deferred which fires with a sequence of buffers. This
        sequence will contain all of the segments of the original data, in
        order. The sum of the lengths of all of the buffers will be the
        'data_size' value passed into the original ICodecEncode.set_params()
        call. To get back the single original input block of data, use
        ''.join(output_buffers), or you may wish to simply write them in
        order to an output file.

        Note that some of the elements in the result sequence may be
        references to the elements of the some_shares input sequence. In
        particular, this means that if those share objects are mutable (e.g.
        arrays) and if they are changed, then both the input (the
        'some_shares' parameter) and the output (the value given when the
        deferred is triggered) will change.

        The length of 'some_shares' is required to be exactly the value of
        'required_shares' passed into the original ICodecEncode.set_params()
        call.
        """

class IEncoder(Interface):
    """I take an object that provides IEncryptedUploadable, which provides
    encrypted data, and a list of shareholders. I then encode, hash, and
    deliver shares to those shareholders. I will compute all the necessary
    Merkle hash trees that are necessary to validate the crypttext that
    eventually comes back from the shareholders. I provide the URI Extension
    Block Hash, and the encoding parameters, both of which must be included
    in the URI.

    I do not choose shareholders, that is left to the IUploader. I must be
    given a dict of RemoteReferences to storage buckets that are ready and
    willing to receive data.
    """

    def set_size(size):
        """Specify the number of bytes that will be encoded. This must be
        peformed before get_serialized_params() can be called.
        """
    def set_params(params):
        """Override the default encoding parameters. 'params' is a tuple of
        (k,d,n), where 'k' is the number of required shares, 'd' is the
        shares_of_happiness, and 'n' is the total number of shares that will
        be created.

        Encoding parameters can be set in three ways. 1: The Encoder class
        provides defaults (3/7/10). 2: the Encoder can be constructed with
        an 'options' dictionary, in which the
        needed_and_happy_and_total_shares' key can be a (k,d,n) tuple. 3:
        set_params((k,d,n)) can be called.

        If you intend to use set_params(), you must call it before
        get_share_size or get_param are called.
        """

    def set_encrypted_uploadable(u):
        """Provide a source of encrypted upload data. 'u' must implement
        IEncryptedUploadable.

        When this is called, the IEncryptedUploadable will be queried for its
        length and the storage_index that should be used.

        This returns a Deferred that fires with this Encoder instance.

        This must be performed before start() can be called.
        """

    def get_param(name):
        """Return an encoding parameter, by name.

        'storage_index': return a string with the (16-byte truncated SHA-256
                         hash) storage index to which these shares should be
                         pushed.

        'share_counts': return a tuple describing how many shares are used:
                        (needed_shares, shares_of_happiness, total_shares)

        'num_segments': return an int with the number of segments that
                        will be encoded.

        'segment_size': return an int with the size of each segment.

        'block_size': return the size of the individual blocks that will
                      be delivered to a shareholder's put_block() method. By
                      knowing this, the shareholder will be able to keep all
                      blocks in a single file and still provide random access
                      when reading them. # TODO: can we avoid exposing this?

        'share_size': an int with the size of the data that will be stored
                      on each shareholder. This is aggregate amount of data
                      that will be sent to the shareholder, summed over all
                      the put_block() calls I will ever make. It is useful to
                      determine this size before asking potential
                      shareholders whether they will grant a lease or not,
                      since their answers will depend upon how much space we
                      need. TODO: this might also include some amount of
                      overhead, like the size of all the hashes. We need to
                      decide whether this is useful or not.

        'serialized_params': a string with a concise description of the
                             codec name and its parameters. This may be passed
                             into the IUploadable to let it make sure that
                             the same file encoded with different parameters
                             will result in different storage indexes.

        Once this is called, set_size() and set_params() may not be called.
        """

    def set_shareholders(shareholders):
        """Tell the encoder where to put the encoded shares. 'shareholders'
        must be a dictionary that maps share number (an integer ranging from
        0 to n-1) to an instance that provides IStorageBucketWriter. This
        must be performed before start() can be called."""

    def start():
        """Begin the encode/upload process. This involves reading encrypted
        data from the IEncryptedUploadable, encoding it, uploading the shares
        to the shareholders, then sending the hash trees.

        set_encrypted_uploadable() and set_shareholders() must be called
        before this can be invoked.

        This returns a Deferred that fires with a tuple of
        (uri_extension_hash, needed_shares, total_shares, size) when the
        upload process is complete. This information, plus the encryption
        key, is sufficient to construct the URI.
        """

class IDecoder(Interface):
    """I take a list of shareholders and some setup information, then
    download, validate, decode, and decrypt data from them, writing the
    results to an output file.

    I do not locate the shareholders, that is left to the IDownloader. I must
    be given a dict of RemoteReferences to storage buckets that are ready to
    send data.
    """

    def setup(outfile):
        """I take a file-like object (providing write and close) to which all
        the plaintext data will be written.

        TODO: producer/consumer . Maybe write() should return a Deferred that
        indicates when it will accept more data? But probably having the
        IDecoder be a producer is easier to glue to IConsumer pieces.
        """

    def set_shareholders(shareholders):
        """I take a dictionary that maps share identifiers (small integers)
        to RemoteReferences that provide RIBucketReader. This must be called
        before start()."""

    def start():
        """I start the download. This process involves retrieving data and
        hash chains from the shareholders, using the hashes to validate the
        data, decoding the shares into segments, decrypting the segments,
        then writing the resulting plaintext to the output file.

        I return a Deferred that will fire (with self) when the download is
        complete.
        """

class IDownloadTarget(Interface):
    def open(size):
        """Called before any calls to write() or close(). If an error
        occurs before any data is available, fail() may be called without
        a previous call to open().

        'size' is the length of the file being downloaded, in bytes."""

    def write(data):
        """Output some data to the target."""
    def close():
        """Inform the target that there is no more data to be written."""
    def fail(why):
        """fail() is called to indicate that the download has failed. 'why'
        is a Failure object indicating what went wrong. No further methods
        will be invoked on the IDownloadTarget after fail()."""
    def register_canceller(cb):
        """The FileDownloader uses this to register a no-argument function
        that the target can call to cancel the download. Once this canceller
        is invoked, no further calls to write() or close() will be made."""
    def finish():
        """When the FileDownloader is done, this finish() function will be
        called. Whatever it returns will be returned to the invoker of
        Downloader.download.
        """

class IDownloader(Interface):
    def download(uri, target):
        """Perform a CHK download, sending the data to the given target.
        'target' must provide IDownloadTarget.

        Returns a Deferred that fires (with the results of target.finish)
        when the download is finished, or errbacks if something went wrong."""

class IEncryptedUploadable(Interface):
    def get_size():
        """This behaves just like IUploadable.get_size()."""

    def set_serialized_encoding_parameters(serialized_encoding_parameters):
        """Tell me what encoding parameters will be used for my data.

        'serialized_encoding_parameters' is a string which indicates how the
        data will be encoded (codec name, blocksize, number of shares).

        I may use this when get_storage_index() is called, to influence the
        index that I return. Or, I may just ignore it.

        set_serialized_encoding_parameters() may be called 0 or 1 times. If
        called, it must be called before get_storage_index().
        """

    def get_storage_index():
        """Return a Deferred that fires with a 16-byte storage index. This
        value may be influenced by the parameters earlier set by
        set_serialized_encoding_parameters().
        """

    def set_segment_size(segment_size):
        """Set the segment size, to allow the IEncryptedUploadable to
        accurately create the plaintext segment hash tree. This must be
        called before any calls to read_encrypted."""

    def read_encrypted(length):
        """This behaves just like IUploadable.read(), but returns crypttext
        instead of plaintext. set_segment_size() must be called before the
        first call to read_encrypted()."""

    def get_plaintext_segment_hashtree_nodes(num_segments):
        """Get the nodes of a merkle hash tree over the plaintext segments.

        This returns a Deferred which fires with a sequence of hashes. Each
        hash is a node of a merkle hash tree, generally obtained from::

         tuple(HashTree(segment_hashes))

        'num_segments' is used to assert that the number of segments that the
        IEncryptedUploadable handled matches the number of segments that the
        encoder was expecting.
        """

    def get_plaintext_hash():
        """Get the hash of the whole plaintext.

        This returns a Deferred which fires with a tagged SHA-256 hash of the
        whole plaintext, obtained from hashutil.plaintext_hash(data).
        """

    def close():
        """Just like IUploadable.close()."""

class IUploadable(Interface):
    def get_size():
        """Return a Deferred that will fire with the length of the data to be
        uploaded, in bytes. This will be called before the data is actually
        used, to compute encoding parameters.
        """

    def set_serialized_encoding_parameters(serialized_encoding_parameters):
        """Tell me what encoding parameters will be used for my data.

        'serialized_encoding_parameters' is a string which indicates how the
        data will be encoded (codec name, blocksize, number of shares).

        I may use this when get_encryption_key() is called, to influence the
        key that I return. Or, I may just ignore it.

        set_serialized_encoding_parameters() may be called 0 or 1 times. If
        called, it must be called before get_encryption_key().
        """

    def get_encryption_key():
        """Return a Deferred that fires with a 16-byte AES key. This key will
        be used to encrypt the data. The key will also be hashed to derive
        the StorageIndex.

        Uploadables which want to achieve convergence should hash their file
        contents and the serialized_encoding_parameters to form the key
        (which of course requires a full pass over the data). Uploadables can
        use the upload.ConvergentUploadMixin class to achieve this
        automatically.

        Uploadables which do not care about convergence (or do not wish to
        make multiple passes over the data) can simply return a
        strongly-random 16 byte string.

        get_encryption_key() may be called multiple times: the IUploadable is
        required to return the same value each time.
        """

    def read(length):
        """Return a Deferred that fires with a list of strings (perhaps with
        only a single element) which, when concatenated together, contain the
        next 'length' bytes of data. If EOF is near, this may provide fewer
        than 'length' bytes. The total number of bytes provided by read()
        before it signals EOF must equal the size provided by get_size().

        If the data must be acquired through multiple internal read
        operations, returning a list instead of a single string may help to
        reduce string copies.

        'length' will typically be equal to (min(get_size(),1MB)/req_shares),
        so a 10kB file means length=3kB, 100kB file means length=30kB,
        and >=1MB file means length=300kB.

        This method provides for a single full pass through the data. Later
        use cases may desire multiple passes or access to only parts of the
        data (such as a mutable file making small edits-in-place). This API
        will be expanded once those use cases are better understood.
        """

    def close():
        """The upload is finished, and whatever filehandle was in use may be
        closed."""

class IUploader(Interface):
    def upload(uploadable):
        """Upload the file. 'uploadable' must impement IUploadable. This
        returns a Deferred which fires with the URI of the file."""

    def upload_ssk(write_capability, new_version, uploadable):
        """TODO: how should this work?"""
    def upload_data(data):
        """Like upload(), but accepts a string."""

    def upload_filename(filename):
        """Like upload(), but accepts an absolute pathname."""

    def upload_filehandle(filehane):
        """Like upload(), but accepts an open filehandle."""

class IChecker(Interface):
    def check(uri_to_check):
        """Accepts an IVerifierURI, and checks upon the health of its target.

        For now, uri_to_check must be an IVerifierURI. In the future we
        expect to relax that to be anything that can be adapted to
        IVerifierURI (like read-only or read-write dirnode/filenode URIs).

        This returns a Deferred. For dirnodes, this fires with either True or
        False (dirnodes are not distributed, so their health is a boolean).

        For filenodes, this fires with a tuple of (needed_shares,
        total_shares, found_shares, sharemap). The first three are ints. The
        basic health of the file is found_shares / needed_shares: if less
        than 1.0, the file is unrecoverable.

        The sharemap has a key for each sharenum. The value is a list of
        (binary) nodeids who hold that share. If two shares are kept on the
        same nodeid, they will fail as a pair, and overall reliability is
        decreased.

        The IChecker instance remembers the results of the check. By default,
        these results are stashed in RAM (and are forgotten at shutdown). If
        a file named 'checker_results.db' exists in the node's basedir, it is
        used as a sqlite database of results, making them persistent across
        runs. To start using this feature, just 'touch checker_results.db',
        and the node will initialize it properly the next time it is started.
        """

    def verify(uri_to_check):
        """Accepts an IVerifierURI, and verifies the crypttext of the target.

        This is a more-intensive form of checking. For verification, the
        file's crypttext contents are retrieved, and the associated hash
        checks are performed. If a storage server is holding a corrupted
        share, verification will detect the problem, but checking will not.
        This returns a Deferred that fires with True if the crypttext hashes
        look good, and will probably raise an exception if anything goes
        wrong.

        For dirnodes, 'verify' is the same as 'check', so the Deferred will
        fire with True or False.

        Verification currently only uses a minimal subset of peers, so a lot
        of share corruption will not be caught by it. We expect to improve
        this in the future.
        """

    def checker_results_for(uri_to_check):
        """Accepts an IVerifierURI, and returns a list of previously recorded
        checker results. This method performs no checking itself: it merely
        reports the results of checks that have taken place in the past.

        Each element of the list is a two-entry tuple: (when, results).
        The 'when' values are timestamps (float seconds since epoch), and the
        results are as defined in the check() method.

        Note: at the moment, this is specified to return synchronously. We
        might need to back away from this in the future.
        """


class IVirtualDrive(Interface):
    """I am a service that may be available to a client.

    Within any client program, this service can be retrieved by using
    client.getService('vdrive').
    """

    def have_public_root():
        """Return a Boolean, True if get_public_root() will work."""
    def get_public_root():
        """Get the public read-write directory root.

        This returns a Deferred that fires with an IDirectoryNode instance
        corresponding to the global shared root directory."""


    def have_private_root():
        """Return a Boolean, True if get_public_root() will work."""
    def get_private_root():
        """Get the private directory root.

        This returns a Deferred that fires with an IDirectoryNode instance
        corresponding to this client's private root directory."""

    def get_node_at_path(path):
        """Transform a path into an IDirectoryNode or IFileNode.

        The path can either be a single string or a list of path-name
        elements. The former is generated from the latter by using
        .join('/'). If the first element of this list is '~', the rest will
        be interpreted relative to the local user's private root directory.
        Otherwse it will be interpreted relative to the global public root
        directory. As a result, the following three values of 'path' are
        equivalent::

         '/dirname/foo.txt'
         'dirname/foo.txt'
         ['dirname', 'foo.txt']

        This method returns a Deferred that fires with the node in question,
        or errbacks with an IndexError if the target node could not be found.
        """

    def get_node(uri):
        """Transform a URI (or IURI) into an IDirectoryNode or IFileNode.

        This returns a Deferred that will fire with an instance that provides
        either IDirectoryNode or IFileNode, as appropriate."""

    def create_directory():
        """Return a new IDirectoryNode that is empty and not linked by
        anything."""


class NotCapableError(Exception):
    """You have tried to write to a read-only node."""

class BadWriteEnablerError(Exception):
    pass


class RIControlClient(RemoteInterface):

    def wait_for_client_connections(num_clients=int):
        """Do not return until we have connections to at least NUM_CLIENTS
        storage servers.
        """

    def upload_from_file_to_uri(filename=str):
        """Upload a file to the grid. This accepts a filename (which must be
        absolute) that points to a file on the node's local disk. The node
        will read the contents of this file, upload it to the grid, then
        return the URI at which it was uploaded.
        """
        return URI

    def download_from_uri_to_file(uri=URI, filename=str):
        """Download a file from the grid, placing it on the node's local disk
        at the given filename (which must be absolute[?]). Returns the
        absolute filename where the file was written."""
        return str

    # debug stuff

    def get_memory_usage():
        """Return a dict describes the amount of memory currently in use. The
        keys are 'VmPeak', 'VmSize', and 'VmData'. The values are integers,
        measuring memory consupmtion in bytes."""
        return DictOf(str, int)

    def speed_test(count=int, size=int):
        """Write 'count' tempfiles to disk, all of the given size. Measure
        how long (in seconds) it takes to upload them all to the servers.
        Then measure how long it takes to download all of them.

        Returns a tuple of (upload_time, download_time).
        """
        return (float, float)

    def measure_peer_response_time():
        """Send a short message to each connected peer, and measure the time
        it takes for them to respond to it. This is a rough measure of the
        application-level round trip time.

        @return: a dictionary mapping peerid to a float (RTT time in seconds)
        """

        return DictOf(Nodeid, float)
