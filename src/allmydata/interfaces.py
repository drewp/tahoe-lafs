
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
StorageIndex = StringConstraint(32)
URI = StringConstraint(300) # kind of arbitrary
MAX_BUCKETS = 200  # per peer
ShareData = StringConstraint(100000) # 2MB segment / k=25
URIExtensionData = StringConstraint(1000)

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


class RIStorageServer(RemoteInterface):
    def allocate_buckets(storage_index=StorageIndex,
                         sharenums=SetOf(int, maxLength=MAX_BUCKETS),
                         allocated_size=int, canary=Referenceable):
        """
        @param canary: If the canary is lost before close(), the bucket is deleted.
        @return: tuple of (alreadygot, allocated), where alreadygot is what we
            already have and is what we hereby agree to accept
        """
        return TupleOf(SetOf(int, maxLength=MAX_BUCKETS),
                       DictOf(int, RIBucketWriter, maxKeys=MAX_BUCKETS))
    def get_buckets(storage_index=StorageIndex):
        return DictOf(int, RIBucketReader, maxKeys=MAX_BUCKETS)


class IStorageBucketWriter(Interface):
    def put_block(segmentnum=int, data=ShareData):
        """@param data: For most segments, this data will be 'blocksize'
        bytes in length. The last segment might be shorter.
        """
        return None

    def put_plaintext_hashes(hashes=ListOf(Hash, maxLength=2**20)):
        return None
    def put_crypttext_hashes(hashes=ListOf(Hash, maxLength=2**20)):
        return None

    def put_block_hashes(blockhashes=ListOf(Hash, maxLength=2**20)):
        return None
        
    def put_share_hashes(sharehashes=ListOf(TupleOf(int, Hash), maxLength=2**20)):
        return None

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
        """
        return None
    def close():
        pass

class IStorageBucketReader(Interface):

    def get_block(blocknum=int):
        """Most blocks will be the same size. The last block might be shorter
        than the others.
        """
        return ShareData

    def get_plaintext_hashes():
        return ListOf(Hash, maxLength=2**20)
    def get_crypttext_hashes():
        return ListOf(Hash, maxLength=2**20)

    def get_block_hashes():
        return ListOf(Hash, maxLength=2**20)
    def get_share_hashes():
        return ListOf(TupleOf(int, Hash), maxLength=2**20)
    def get_uri_extension():
        return URIExtensionData



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
        return URI

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
        """Set a child object.

        This will raise IndexError if a child with the given name already
        exists.
        """

    def delete(index=Hash, write_enabler=Hash, key=Hash):
        """Delete a specific child.

        This uses the hashed key to locate a specific child, and deletes it.
        """


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

    def get_refresh_capability():
        """Return a string that represents the 'refresh capability' for this
        node. The holder of this capability will be able to renew the lease
        for this node, protecting it from garbage-collection.
        """

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

    def get_refresh_capability():
        """Return a string that represents the 'refresh capability' for this
        node. The holder of this capability will be able to renew the lease
        for this node, protecting it from garbage-collection.
        """

    def list():
        """I return a Deferred that fires with a dictionary mapping child
        name to an IFileNode or IDirectoryNode."""

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
        that fires when the operation finishes.

        The child_uri could be for a file, or for a directory (either
        read-write or read-only, using a URI that came from get_uri() ).

        If this directory node is read-only, the Deferred will errback with a
        NotMutableError."""

    def set_node(name, child):
        """I add a child at the specific name. I return a Deferred that fires
        when the operation finishes. This Deferred will fire with the child
        node that was just added.

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
        """Return a set of refresh-capabilities for all nodes (directories
        and files) reachable from this one."""

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
    """I take a file-like object that provides a sequence of bytes and a list
    of shareholders, then encrypt, encode, hash, and deliver shares to those
    shareholders. I will compute all the necessary Merkle hash trees that are
    necessary to validate the data that eventually comes back from the
    shareholders. I provide the root hash of the hash tree, and the encoding
    parameters, both of which must be included in the URI.

    I do not choose shareholders, that is left to the IUploader. I must be
    given a dict of RemoteReferences to storage buckets that are ready and
    willing to receive data.
    """

    def setup(infile):
        """I take a file-like object (providing seek, tell, and read) from
        which all the plaintext data that is to be uploaded can be read. I
        will seek to the beginning of the file before reading any data.
        setup() must be called before making any other calls, in particular
        before calling get_reservation_size().
        """

    def get_share_size():
        """I return the size of the data that will be stored on each
        shareholder. This is aggregate amount of data that will be sent to
        the shareholder, summed over all the put_block() calls I will ever
        make.

        TODO: this might also include some amount of overhead, like the size
        of all the hashes. We need to decide whether this is useful or not.

        It is useful to determine this size before asking potential
        shareholders whether they will grant a lease or not, since their
        answers will depend upon how much space we need.
        """

    def get_block_size(): # TODO: can we avoid exposing this?
        """I return the size of the individual blocks that will be delivered
        to a shareholder's put_block() method. By knowing this, the
        shareholder will be able to keep all blocks in a single file and
        still provide random access when reading them.
        """

    def set_shareholders(shareholders):
        """I take a dictionary that maps share identifiers (small integers,
        starting at 0) to RemoteReferences that provide RIBucketWriter. This
        must be called before start().
        """

    def start():
        """I start the upload. This process involves reading data from the
        input file, encrypting it, encoding the pieces, uploading the shares
        to the shareholders, then sending the hash trees.

        I return a Deferred that fires with the hash of the uri_extension
        data block.
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

class IUploadable(Interface):
    def get_filehandle():
        """Return a filehandle from which the data to be uploaded can be
        read. It must implement .read, .seek, and .tell (since the latter two
        are used to determine the length of the data)."""
    def close_filehandle(f):
        """The upload is finished. This provides the same filehandle as was
        returned by get_filehandle. This is an appropriate place to close the
        filehandle."""

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
        """Transform a URI into an IDirectoryNode or IFileNode.

        This returns a Deferred that will fire with an instance that provides
        either IDirectoryNode or IFileNode, as appropriate."""

class NotCapableError(Exception):
    """You have tried to write to a read-only node."""

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
