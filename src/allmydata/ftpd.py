
import os
import tempfile
from zope.interface import implements
from twisted.application import service, strports
from twisted.internet import defer
from twisted.internet.interfaces import IConsumer
from twisted.protocols import ftp
from twisted.cred import error, portal, checkers, credentials
from twisted.python import log

from allmydata.interfaces import IDirectoryNode, ExistingChildError
from allmydata.immutable.download import ConsumerAdapter
from allmydata.immutable.upload import FileHandle

class ReadFile:
    implements(ftp.IReadFile)
    def __init__(self, node):
        self.node = node
    def send(self, consumer):
        print "SEND", consumer
        ad = ConsumerAdapter(consumer)
        d = self.node.download(ad)
        def _downloaded(res):
            print "DONE"
        d.addCallback(_downloaded)
        return d # when consumed

class FileWriter:
    implements(IConsumer)
    def __init__(self, parent, childname, convergence):
        self.parent = parent
        self.childname = childname
        self.convergence = convergence

    def registerProducer(self, producer, streaming):
        self.producer = producer
        print "producer", producer
        print "streaming", streaming
        if not streaming:
            raise NotImplementedError("Non-streaming producer not supported.")
        # we write the data to a temporary file, since Tahoe can't do
        # streaming upload yet.
        self.f = tempfile.TemporaryFile()
        return None
    def unregisterProducer(self):
        # now we do the upload.

        # bummer: unregisterProducer is run synchronously. twisted's FTP
        # server (twisted.protocols.ftp.DTP._unregConsumer:454) ignores our
        # return value, and sends the 226 Transfer Complete right after
        # unregisterProducer returns. The client will believe that the
        # transfer is indeed complete, whereas for us it is just starting.
        # Some clients will do an immediate LIST to see if the file was
        # really uploaded.
        print "UPLOAD STSARTING"
        u = FileHandle(self.f, self.convergence)
        d = self.parent.add_file(self.childname, u)
        def _done(res):
            print "UPLOAD DONE", res
        d.addCallback(_done)
        # by patching twisted.protocols.ftp.DTP._unregConsumer to pass this
        # Deferred back, we can obtain the async-upload that we desire.
        return d

    def write(self, data):
        print "write(%d)" % len(data)
        # if streaming==True, then the sender/producer is in charge. We are
        # allowed to call self.producer.pauseProducing() when we have too
        # much data and want them to stop, but they might not listen to us.
        # We must then call self.producer.resumeProducing() when we can
        # accomodate more.
        #
        # if streaming==False, then we (the consumer) are in charge. We must
        # keep calling p.resumeProducing() (which will prompt them to call
        # our .write again) until they finish.
        #
        # If we experience an error, call p.stopProducing().
        self.f.write(data)

class WriteFile:
    implements(ftp.IWriteFile)
    def __init__(self, parent, childname, convergence):
        self.parent = parent
        self.childname = childname
        self.convergence = convergence
    def receive(self):
        print "RECEIVE"
        try:
            c = FileWriter(self.parent, self.childname, self.convergence)
        except:
            print "PROBLEM"
            log.err()
            raise
        return defer.succeed(c)

class NoParentError(Exception):
    pass

class Handler:
    implements(ftp.IFTPShell)
    def __init__(self, client, rootnode, username, convergence):
        self.client = client
        self.root = rootnode
        self.username = username
        self.convergence = convergence

    def makeDirectory(self, path):
        print "MAKEDIR", path
        d = self._get_root(path)
        d.addCallback(lambda (root,path):
                      self._get_or_create_directories(root, path))
        return d

    def _get_or_create_directories(self, node, path):
        if not IDirectoryNode.providedBy(node):
            # unfortunately it is too late to provide the name of the
            # blocking directory in the error message.
            raise ftp.FileExistsError("cannot create directory because there "
                                      "is a file in the way")
        if not path:
            return defer.succeed(node)
        d = node.get(path[0])
        def _maybe_create(f):
            f.trap(KeyError)
            return node.create_empty_directory(path[0])
        d.addErrback(_maybe_create)
        d.addCallback(self._get_or_create_directories, path[1:])
        return d

    def _get_parent(self, path):
        # fire with (parentnode, childname)
        path = [unicode(p) for p in path]
        if not path:
            raise NoParentError
        childname = path[-1]
        d = self._get_root(path)
        def _got_root((root, path)):
            print "GOT ROOT", root, path
            if not path:
                raise NoParentError
            return root.get_child_at_path(path[:-1])
        d.addCallback(_got_root)
        def _got_parent(parent):
            return (parent, childname)
        d.addCallback(_got_parent)
        return d

    def _remove_thing(self, path, must_be_directory=False, must_be_file=False):
        d = defer.maybeDeferred(self._get_parent, path)
        def _convert_error(f):
            f.trap(NoParentError)
            raise ftp.PermissionDeniedError("cannot delete root directory")
        d.addErrback(_convert_error)
        def _got_parent( (parent, childname) ):
            print "GOT PARENT", parent
            d = parent.get(childname)
            def _got_child(child):
                print "GOT HILD", child
                if must_be_directory and not IDirectoryNode.providedBy(child):
                    raise ftp.IsNotADirectoryError("rmdir called on a file")
                if must_be_file and IDirectoryNode.providedBy(child):
                    raise ftp.IsADirectoryError("rmfile called on a directory")
                return parent.delete(childname)
            d.addCallback(_got_child)
            d.addErrback(self._convert_error)
            return d
        d.addCallback(_got_parent)
        return d

    def removeDirectory(self, path):
        print "RMDIR", path
        return self._remove_thing(path, must_be_directory=True)

    def removeFile(self, path):
        print "RM", path
        return self._remove_thing(path, must_be_file=True)

    def rename(self, fromPath, toPath):
        print "MV", fromPath, toPath
        # the target directory must already exist
        d = self._get_parent(fromPath)
        def _got_from_parent( (fromparent, childname) ):
            d = self._get_parent(toPath)
            d.addCallback(lambda (toparent, tochildname):
                          fromparent.move_child_to(childname,
                                                   toparent, tochildname,
                                                   overwrite=False))
            return d
        d.addCallback(_got_from_parent)
        d.addErrback(self._convert_error)
        return d

    def access(self, path):
        print "ACCESS", path
        # we allow access to everything that exists. We are required to raise
        # an error for paths that don't exist: FTP clients (at least ncftp)
        # uses this to decide whether to mkdir or not.
        d = self._get_node_and_metadata_for_path(path)
        d.addErrback(self._convert_error)
        d.addCallback(lambda res: None)
        return d

    def _convert_error(self, f):
        if f.check(KeyError):
            childname = f.value.args[0].encode("utf-8")
            msg = "'%s' doesn't exist" % childname
            raise ftp.FileNotFoundError(msg)
        if f.check(ExistingChildError):
            msg = f.value.args[0].encode("utf-8")
            raise ftp.FileExistsError(msg)
        return f

    def _get_root(self, path):
        # return (root, remaining_path)
        path = [unicode(p) for p in path]
        if path and path[0] == "uri":
            d = defer.maybeDeferred(self.client.create_node_from_uri,
                                    str(path[1]))
            d.addCallback(lambda root: (root, path[2:]))
        else:
            d = defer.succeed((self.root,path))
        return d

    def _get_node_and_metadata_for_path(self, path):
        d = self._get_root(path)
        def _got_root((root,path)):
            if path:
                return root.get_child_and_metadata_at_path(path)
            else:
                return (root,{})
        d.addCallback(_got_root)
        return d

    def _populate_row(self, keys, (childnode, metadata)):
        print childnode.get_uri(), metadata
        values = []
        isdir = bool(IDirectoryNode.providedBy(childnode))
        for key in keys:
            if key == "size":
                if isdir:
                    value = 0
                else:
                    value = childnode.get_size()
            elif key == "directory":
                value = isdir
            elif key == "permissions":
                value = 0600
            elif key == "hardlinks":
                value = 1
            elif key == "modified":
                value = metadata.get("mtime", 0)
            elif key == "owner":
                value = self.username
            elif key == "group":
                value = self.username
            else:
                value = "??"
            values.append(value)
        return values

    def stat(self, path, keys=()):
        # for files only, I think
        print "STAT", path, keys
        d = self._get_node_and_metadata_for_path(path)
        def _render((node,metadata)):
            assert not IDirectoryNode.providedBy(node)
            return self._populate_row(keys, (node,metadata))
        d.addCallback(_render)
        d.addErrback(self._convert_error)
        return d

    def list(self, path, keys=()):
        print "LIST", repr(path), repr(keys)
        # the interface claims that path is a list of unicodes, but in
        # practice it is not
        d = self._get_node_and_metadata_for_path(path)
        def _list((node, metadata)):
            if IDirectoryNode.providedBy(node):
                return node.list()
            return { path[-1]: (node, metadata) } # need last-edge metadata
        d.addCallback(_list)
        def _render(children):
            results = []
            for (name, childnode) in children.iteritems():
                # the interface claims that the result should have a unicode
                # object as the name, but it fails unless you give it a
                # bytestring
                results.append( (name.encode("utf-8"),
                                 self._populate_row(keys, childnode) ) )
            print repr(results)
            return results
        d.addCallback(_render)
        d.addErrback(self._convert_error)
        return d

    def openForReading(self, path):
        print "OPEN-READ", path
        d = self._get_node_and_metadata_for_path(path)
        d.addCallback(lambda (node,metadata): ReadFile(node))
        d.addErrback(self._convert_error)
        return d

    def openForWriting(self, path):
        print "OPEN-WRITE", path
        path = [unicode(p) for p in path]
        if not path:
            raise ftp.PermissionDeniedError("cannot STOR to root directory")
        childname = path[-1]
        d = self._get_root(path)
        def _got_root((root, path)):
            print "GOT ROOT", root, path
            if not path:
                raise ftp.PermissionDeniedError("cannot STOR to root directory")
            return root.get_child_at_path(path[:-1])
        d.addCallback(_got_root)
        def _got_parent(parent):
            return WriteFile(parent, childname, self.convergence)
        d.addCallback(_got_parent)
        return d


class FTPAvatarID:
    def __init__(self, username, rootcap):
        self.username = username
        self.rootcap = rootcap

class AccountFileChecker:
    implements(checkers.ICredentialsChecker)
    credentialInterfaces = (credentials.IUsernamePassword,
                            credentials.IUsernameHashedPassword)
    def __init__(self, client, accountfile):
        self.client = client
        self.passwords = {}
        self.rootcaps = {}
        for line in open(os.path.expanduser(accountfile), "r"):
            line = line.strip()
            if line.startswith("#") or not line:
                continue
            name, passwd, rootcap = line.split()
            self.passwords[name] = passwd
            self.rootcaps[name] = rootcap

    def _cbPasswordMatch(self, matched, username):
        if matched:
            return FTPAvatarID(username, self.rootcaps[username])
        raise error.UnauthorizedLogin

    def requestAvatarId(self, credentials):
        if credentials.username in self.passwords:
            d = defer.maybeDeferred(credentials.checkPassword,
                                    self.passwords[credentials.username])
            d.addCallback(self._cbPasswordMatch, str(credentials.username))
            return d
        return defer.fail(error.UnauthorizedLogin())

class Dispatcher:
    implements(portal.IRealm)
    def __init__(self, client):
        self.client = client

    def requestAvatar(self, avatarID, mind, interface):
        assert interface == ftp.IFTPShell
        print "REQUEST", avatarID, mind, interface
        rootnode = self.client.create_node_from_uri(avatarID.rootcap)
        convergence = self.client.convergence
        s = Handler(self.client, rootnode, avatarID.username, convergence)
        return (interface, s, None)


class FTPServer(service.MultiService):
    def __init__(self, client, portstr, accountfile, accounturl):
        service.MultiService.__init__(self)

        if accountfile:
            c = AccountFileChecker(self, accountfile)
        elif accounturl:
            raise NotImplementedError("account URL not yet implemented")
        else:
            # we could leave this anonymous, with just the /uri/CAP form
            raise RuntimeError("must provide some translation")

        r = Dispatcher(client)
        p = portal.Portal(r)
        p.registerChecker(c)
        f = ftp.FTPFactory(p)

        s = strports.service(portstr, f)
        s.setServiceParent(self)
