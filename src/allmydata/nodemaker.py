import weakref
from zope.interface import implements
from allmydata.interfaces import INodeMaker
from allmydata.immutable.literal import LiteralFileNode
from allmydata.immutable.filenode import ImmutableFileNode, CiphertextFileNode
from allmydata.immutable.upload import Data
from allmydata.mutable.filenode import MutableFileNode
from allmydata.dirnode import DirectoryNode, pack_children
from allmydata.unknown import UnknownNode
from allmydata import uri

class NodeMaker:
    implements(INodeMaker)

    def __init__(self, storage_broker, secret_holder, history,
                 uploader, terminator,
                 default_encoding_parameters, key_generator):
        self.storage_broker = storage_broker
        self.secret_holder = secret_holder
        self.history = history
        self.uploader = uploader
        self.terminator = terminator
        self.default_encoding_parameters = default_encoding_parameters
        self.key_generator = key_generator

        self._node_cache = weakref.WeakValueDictionary() # uri -> node

    def _create_lit(self, cap):
        return LiteralFileNode(cap)
    def _create_immutable(self, cap):
        return ImmutableFileNode(cap, self.storage_broker, self.secret_holder,
                                 self.terminator, self.history)
    def _create_immutable_verifier(self, cap):
        return CiphertextFileNode(cap, self.storage_broker, self.secret_holder,
                                  self.terminator, self.history)
    def _create_mutable(self, cap):
        n = MutableFileNode(self.storage_broker, self.secret_holder,
                            self.default_encoding_parameters,
                            self.history)
        return n.init_from_cap(cap)
    def _create_dirnode(self, filenode):
        return DirectoryNode(filenode, self, self.uploader)

    def create_from_cap(self, writecap, readcap=None, deep_immutable=False, name=u"<unknown name>"):
        # this returns synchronously. It starts with a "cap string".
        assert isinstance(writecap, (str, type(None))), type(writecap)
        assert isinstance(readcap,  (str, type(None))), type(readcap)

        bigcap = writecap or readcap
        if not bigcap:
            # maybe the writecap was hidden because we're in a readonly
            # directory, and the future cap format doesn't have a readcap, or
            # something.
            return UnknownNode(None, None)  # deep_immutable and name not needed

        # The name doesn't matter for caching since it's only used in the error
        # attribute of an UnknownNode, and we don't cache those.
        if deep_immutable:
            memokey = "I" + bigcap
        else:
            memokey = "M" + bigcap
        if memokey in self._node_cache:
            return self._node_cache[memokey]
        cap = uri.from_string(bigcap, deep_immutable=deep_immutable, name=name)
        node = self._create_from_single_cap(cap)
        if node:
            self._node_cache[memokey] = node  # note: WeakValueDictionary
        else:
            # don't cache UnknownNode
            node = UnknownNode(writecap, readcap, deep_immutable=deep_immutable, name=name)
        return node

    def _create_from_single_cap(self, cap):
        if isinstance(cap, uri.LiteralFileURI):
            return self._create_lit(cap)
        if isinstance(cap, uri.CHKFileURI):
            return self._create_immutable(cap)
        if isinstance(cap, uri.CHKFileVerifierURI):
            return self._create_immutable_verifier(cap)
        if isinstance(cap, (uri.ReadonlySSKFileURI, uri.WriteableSSKFileURI)):
            return self._create_mutable(cap)
        if isinstance(cap, (uri.DirectoryURI,
                            uri.ReadonlyDirectoryURI,
                            uri.ImmutableDirectoryURI,
                            uri.LiteralDirectoryURI)):
            filenode = self._create_from_single_cap(cap.get_filenode_cap())
            return self._create_dirnode(filenode)
        return None

    def create_mutable_file(self, contents=None, keysize=None):
        n = MutableFileNode(self.storage_broker, self.secret_holder,
                            self.default_encoding_parameters, self.history)
        d = self.key_generator.generate(keysize)
        d.addCallback(n.create_with_keys, contents)
        d.addCallback(lambda res: n)
        return d

    def create_new_mutable_directory(self, initial_children={}):
        d = self.create_mutable_file(lambda n:
                                     pack_children(initial_children, n.get_writekey()))
        d.addCallback(self._create_dirnode)
        return d

    def create_immutable_directory(self, children, convergence=None):
        if convergence is None:
            convergence = self.secret_holder.get_convergence_secret()
        packed = pack_children(children, None, deep_immutable=True)
        uploadable = Data(packed, convergence)
        d = self.uploader.upload(uploadable, history=self.history)
        d.addCallback(lambda results: self.create_from_cap(None, results.uri))
        d.addCallback(self._create_dirnode)
        return d
