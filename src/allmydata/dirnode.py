
import os.path
from zope.interface import implements
from twisted.application import service
from twisted.internet import defer
from foolscap import Referenceable
from allmydata import uri
from allmydata.interfaces import RIVirtualDriveServer, \
     IDirectoryNode, IFileNode, IFileURI, IDirnodeURI, IURI
from allmydata.util import bencode, idlib, hashutil, fileutil
from allmydata.Crypto.Cipher import AES

# VirtualDriveServer is the side that hosts directory nodes

class BadWriteEnablerError(Exception):
    pass
class ChildAlreadyPresentError(Exception):
    pass

class NoPublicRootError(Exception):
    pass

class VirtualDriveServer(service.MultiService, Referenceable):
    implements(RIVirtualDriveServer)
    name = "filetable"

    def __init__(self, basedir, offer_public_root=True):
        service.MultiService.__init__(self)
        self._basedir = os.path.abspath(basedir)
        fileutil.make_dirs(self._basedir)
        self._root = None
        if offer_public_root:
            rootfile = os.path.join(self._basedir, "root")
            if not os.path.exists(rootfile):
                write_key = hashutil.random_key()
                (wk, we, rk, index) = \
                     hashutil.generate_dirnode_keys_from_writekey(write_key)
                self.create_directory(index, we)
                f = open(rootfile, "wb")
                f.write(wk)
                f.close()
                self._root = wk
            else:
                f = open(rootfile, "rb")
                self._root = f.read()

    def set_furl(self, myfurl):
        self._myfurl = myfurl

    def get_public_root_uri(self):
        if self._root:
            u = uri.DirnodeURI(self._myfurl, self._root)
            return u.to_string()
        raise NoPublicRootError
    remote_get_public_root_uri = get_public_root_uri

    def create_directory(self, index, write_enabler):
        data = [write_enabler, []]
        self._write_to_file(index, data)
        return index
    remote_create_directory = create_directory

    # the file on disk consists of the write_enabler token and a list of
    # (H(name), E(name), E(write), E(read)) tuples.

    def _read_from_file(self, index):
        name = idlib.b2a(index)
        data = open(os.path.join(self._basedir, name), "rb").read()
        return bencode.bdecode(data)

    def _write_to_file(self, index, data):
        name = idlib.b2a(index)
        f = open(os.path.join(self._basedir, name), "wb")
        f.write(bencode.bencode(data))
        f.close()


    def get(self, index, key):
        data = self._read_from_file(index)
        for (H_key, E_key, E_write, E_read) in data[1]:
            if H_key == key:
                return (E_write, E_read)
        raise KeyError("unable to find key %s" % idlib.b2a(key))
    remote_get = get

    def list(self, index):
        data = self._read_from_file(index)
        response = [ (E_key, E_write, E_read)
                     for (H_key, E_key, E_write, E_read) in data[1] ]
        return response
    remote_list = list

    def delete(self, index, write_enabler, key):
        data = self._read_from_file(index)
        if data[0] != write_enabler:
            raise BadWriteEnablerError
        for i,(H_key, E_key, E_write, E_read) in enumerate(data[1]):
            if H_key == key:
                del data[1][i]
                self._write_to_file(index, data)
                return
        raise KeyError("unable to find key %s" % idlib.b2a(key))
    remote_delete = delete

    def set(self, index, write_enabler, key,   name, write, read):
        data = self._read_from_file(index)
        if data[0] != write_enabler:
            raise BadWriteEnablerError
        # first, see if the key is already present
        for i,(H_key, E_key, E_write, E_read) in enumerate(data[1]):
            if H_key == key:
                raise ChildAlreadyPresentError
        # now just append the data
        data[1].append( (key, name, write, read) )
        self._write_to_file(index, data)
    remote_set = set

# whereas ImmutableDirectoryNodes and their support mechanisms live on the
# client side

class NotMutableError(Exception):
    pass


def create_directory_node(client, diruri):
    u = IURI(diruri)
    assert IDirnodeURI.providedBy(u)
    d = client.tub.getReference(u.furl)
    def _got(rref):
        if isinstance(u, uri.DirnodeURI):
            return MutableDirectoryNode(u, client, rref)
        else: # uri.ReadOnlyDirnodeURI
            return ImmutableDirectoryNode(u, client, rref)
    d.addCallback(_got)
    return d

IV_LENGTH = 14
def encrypt(key, data):
    IV = os.urandom(IV_LENGTH)
    counterstart = IV + "\x00"*(16-IV_LENGTH)
    assert len(counterstart) == 16, len(counterstart)
    cryptor = AES.new(key=key, mode=AES.MODE_CTR, counterstart=counterstart)
    crypttext = cryptor.encrypt(data)
    mac = hashutil.hmac(key, IV + crypttext)
    assert len(mac) == 32
    return IV + crypttext + mac

class IntegrityCheckError(Exception):
    pass

def decrypt(key, data):
    assert len(data) >= (32+IV_LENGTH), len(data)
    IV, crypttext, mac = data[:IV_LENGTH], data[IV_LENGTH:-32], data[-32:]
    if mac != hashutil.hmac(key, IV+crypttext):
        raise IntegrityCheckError("HMAC does not match, crypttext is corrupted")
    counterstart = IV + "\x00"*(16-IV_LENGTH)
    assert len(counterstart) == 16, len(counterstart)
    cryptor = AES.new(key=key, mode=AES.MODE_CTR, counterstart=counterstart)
    plaintext = cryptor.decrypt(crypttext)
    return plaintext


class ImmutableDirectoryNode:
    implements(IDirectoryNode)

    def __init__(self, myuri, client, rref):
        u = IDirnodeURI(myuri)
        assert u.is_readonly()
        self._uri = u.to_string()
        self._client = client
        self._tub = client.tub
        self._rref = rref
        self._readkey = u.readkey
        self._writekey = None
        self._write_enabler = None
        self._index = hashutil.dir_index_hash(self._readkey)
        self._mutable = False

    def dump(self):
        return ["URI: %s" % self._uri,
                "rk: %s" % idlib.b2a(self._readkey),
                "index: %s" % idlib.b2a(self._index),
                ]

    def is_mutable(self):
        return self._mutable

    def get_uri(self):
        return self._uri

    def get_immutable_uri(self):
        # return the dirnode URI for a read-only form of this directory
        return IDirnodeURI(self._uri).get_readonly().to_string()

    def __hash__(self):
        return hash((self.__class__, self._uri))
    def __cmp__(self, them):
        if cmp(type(self), type(them)):
            return cmp(type(self), type(them))
        if cmp(self.__class__, them.__class__):
            return cmp(self.__class__, them.__class__)
        return cmp(self._uri, them._uri)

    def _encrypt(self, key, data):
        return encrypt(key, data)

    def _decrypt(self, key, data):
        return decrypt(key, data)

    def _decrypt_child(self, E_write, E_read):
        if E_write and self._writekey:
            # we prefer read-write children when we can get them
            return self._decrypt(self._writekey, E_write)
        else:
            return self._decrypt(self._readkey, E_read)

    def list(self):
        d = self._rref.callRemote("list", self._index)
        entries = {}
        def _got(res):
            dl = []
            for (E_name, E_write, E_read) in res:
                name = self._decrypt(self._readkey, E_name)
                child_uri = self._decrypt_child(E_write, E_read)
                d2 = self._create_node(child_uri)
                def _created(node, name):
                    entries[name] = node
                d2.addCallback(_created, name)
                dl.append(d2)
            return defer.DeferredList(dl)
        d.addCallback(_got)
        d.addCallback(lambda res: entries)
        return d

    def _hash_name(self, name):
        return hashutil.dir_name_hash(self._readkey, name)

    def get(self, name):
        H_name = self._hash_name(name)
        d = self._rref.callRemote("get", self._index, H_name)
        def _check_index_error(f):
            f.trap(KeyError)
            raise KeyError("get(index=%s): unable to find child named '%s'"
                           % (idlib.b2a(self._index), name))
        d.addErrback(_check_index_error)
        d.addCallback(lambda (E_write, E_read):
                      self._decrypt_child(E_write, E_read))
        d.addCallback(self._create_node)
        return d

    def _set(self, name, write_child, read_child):
        if not self._mutable:
            return defer.fail(NotMutableError())
        H_name = self._hash_name(name)
        E_name = self._encrypt(self._readkey, name)
        E_write = ""
        if self._writekey and write_child:
            assert isinstance(write_child, str)
            E_write = self._encrypt(self._writekey, write_child)
        assert isinstance(read_child, str)
        E_read = self._encrypt(self._readkey, read_child)
        d = self._rref.callRemote("set", self._index, self._write_enabler,
                                  H_name, E_name, E_write, E_read)
        return d

    def set_uri(self, name, child_uri):
        write, read = self._split_uri(child_uri)
        return self._set(name, write, read)

    def set_node(self, name, child):
        d = self.set_uri(name, child.get_uri())
        d.addCallback(lambda res: child)
        return d

    def delete(self, name):
        if not self._mutable:
            return defer.fail(NotMutableError())
        H_name = self._hash_name(name)
        d = self._rref.callRemote("delete", self._index, self._write_enabler,
                                  H_name)
        return d

    def _create_node(self, child_uri):
        u = IURI(child_uri)
        if IDirnodeURI.providedBy(u):
            return create_directory_node(self._client, u)
        else:
            return defer.succeed(FileNode(u, self._client))

    def _split_uri(self, child_uri):
        u = IURI(child_uri)
        if u.is_mutable() and not u.is_readonly():
            write = u.to_string()
        else:
            write = None
        read = u.get_readonly().to_string()
        return (write, read)

    def create_empty_directory(self, name):
        if not self._mutable:
            return defer.fail(NotMutableError())
        child_writekey = hashutil.random_key()
        furl = IDirnodeURI(self._uri).furl
        u = uri.DirnodeURI(furl, child_writekey)
        child = MutableDirectoryNode(u, self._client, self._rref)
        d = self._rref.callRemote("create_directory",
                                  child._index, child._write_enabler)
        d.addCallback(lambda index: self.set_node(name, child))
        return d

    def add_file(self, name, uploadable):
        if not self._mutable:
            return defer.fail(NotMutableError())
        uploader = self._client.getServiceNamed("uploader")
        d = uploader.upload(uploadable)
        d.addCallback(lambda uri: self.set_node(name,
                                                FileNode(uri, self._client)))
        return d

    def move_child_to(self, current_child_name,
                      new_parent, new_child_name=None):
        if not (self._mutable and new_parent.is_mutable()):
            return defer.fail(NotMutableError())
        if new_child_name is None:
            new_child_name = current_child_name
        d = self.get(current_child_name)
        d.addCallback(lambda child: new_parent.set_node(new_child_name, child))
        d.addCallback(lambda child: self.delete(current_child_name))
        return d

    def build_manifest(self):
        # given a dirnode, construct a list refresh-capabilities for all the
        # nodes it references.

        # this is just a tree-walker, except that following each edge
        # requires a Deferred.

        manifest = set()
        manifest.add(self.get_refresh_capability())

        d = self._build_manifest_from_node(self, manifest)
        # LIT nodes have no refresh-capability: their data is stored inside
        # the URI itself, so there is no need to refresh anything. They
        # indicate this by returning None from their get_refresh_capability
        # method. We need to remove any such Nones from our set.
        d.addCallback(lambda res: manifest.discard(None))
        d.addCallback(lambda res: manifest)
        return d

    def _build_manifest_from_node(self, node, manifest):
        d = node.list()
        def _got_list(res):
            dl = []
            for name, child in res.iteritems():
                manifest.add(child.get_refresh_capability())
                if IDirectoryNode.providedBy(child) and child not in manifest:
                    dl.append(self._build_manifest_from_node(child, manifest))
            if dl:
                return defer.DeferredList(dl)
        d.addCallback(_got_list)
        return d

    def get_refresh_capability(self):
        u = IDirnodeURI(self._uri).get_readonly()
        rk = u.readkey
        wk, we, rk, index = hashutil.generate_dirnode_keys_from_readkey(rk)
        return "DIR-REFRESH:%s" % idlib.b2a(index)

    def get_child_at_path(self, path):
        if not path:
            return defer.succeed(self)
        if isinstance(path, (str, unicode)):
            path = path.split("/")
        childname = path[0]
        remaining_path = path[1:]
        d = self.get(childname)
        if remaining_path:
            def _got(node):
                return node.get_child_at_path(remaining_path)
            d.addCallback(_got)
        return d

class MutableDirectoryNode(ImmutableDirectoryNode):
    implements(IDirectoryNode)

    def __init__(self, myuri, client, rref):
        u = IDirnodeURI(myuri)
        assert not u.is_readonly()
        self._writekey = u.writekey
        self._write_enabler = hashutil.dir_write_enabler_hash(u.writekey)
        readkey = hashutil.dir_read_key_hash(u.writekey)
        self._uri = u.to_string()
        self._client = client
        self._tub = client.tub
        self._rref = rref
        self._readkey = readkey
        self._index = hashutil.dir_index_hash(self._readkey)
        self._mutable = True

def create_directory(client, furl):
    write_key = hashutil.random_key()
    (wk, we, rk, index) = \
         hashutil.generate_dirnode_keys_from_writekey(write_key)
    u = uri.DirnodeURI(furl, wk)
    d = client.tub.getReference(furl)
    def _got_vdrive_server(vdrive_server):
        node = MutableDirectoryNode(u, client, vdrive_server)
        d2 = vdrive_server.callRemote("create_directory", index, we)
        d2.addCallback(lambda res: node)
        return d2
    d.addCallback(_got_vdrive_server)
    return d

class FileNode:
    implements(IFileNode)

    def __init__(self, uri, client):
        u = IFileURI(uri)
        self.uri = u.to_string()
        self._client = client

    def get_uri(self):
        return self.uri

    def get_size(self):
        return IFileURI(self.uri).get_size()

    def __hash__(self):
        return hash((self.__class__, self.uri))
    def __cmp__(self, them):
        if cmp(type(self), type(them)):
            return cmp(type(self), type(them))
        if cmp(self.__class__, them.__class__):
            return cmp(self.__class__, them.__class__)
        return cmp(self.uri, them.uri)

    def get_refresh_capability(self):
        u = IFileURI(self.uri)
        if isinstance(u, uri.CHKFileURI):
            return "CHK-REFRESH:%s" % idlib.b2a(u.storage_index)
        return None

    def download(self, target):
        downloader = self._client.getServiceNamed("downloader")
        return downloader.download(self.uri, target)

    def download_to_data(self):
        downloader = self._client.getServiceNamed("downloader")
        return downloader.download_to_data(self.uri)

