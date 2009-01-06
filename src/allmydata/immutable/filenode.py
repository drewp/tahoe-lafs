
import os.path, stat
from cStringIO import StringIO
from zope.interface import implements
from twisted.internet import defer
from twisted.internet.interfaces import IPushProducer, IConsumer
from twisted.protocols import basic
from foolscap.eventual import eventually
from allmydata.interfaces import IFileNode, IFileURI, ICheckable, \
     IDownloadTarget
from allmydata.util import log, base32
from allmydata.immutable.checker import Checker
from allmydata.check_results import CheckAndRepairResults
from allmydata.immutable.repairer import Repairer
from allmydata.immutable import download

class _ImmutableFileNodeBase(object):
    implements(IFileNode, ICheckable)

    def __init__(self, uri, client):
        self.u = IFileURI(uri)
        self._client = client

    def get_readonly_uri(self):
        return self.get_uri()

    def is_mutable(self):
        return False

    def is_readonly(self):
        return True

    def __hash__(self):
        return self.u.__hash__()
    def __eq__(self, other):
        if IFileNode.providedBy(other):
            return self.u.__eq__(other.u)
        else:
            return False
    def __ne__(self, other):
        if IFileNode.providedBy(other):
            return self.u.__eq__(other.u)
        else:
            return True

class PortionOfFile:
    # like a list slice (things[2:14]), but for a file on disk
    def __init__(self, fn, offset=0, size=None):
        self.f = open(fn, "rb")
        self.f.seek(offset)
        self.bytes_left = size

    def read(self, size=None):
        # bytes_to_read = min(size, self.bytes_left), but None>anything
        if size is None:
            bytes_to_read = self.bytes_left
        elif self.bytes_left is None:
            bytes_to_read = size
        else:
            bytes_to_read = min(size, self.bytes_left)
        data = self.f.read(bytes_to_read)
        if self.bytes_left is not None:
            self.bytes_left -= len(data)
        return data

class DownloadCache:
    implements(IDownloadTarget)

    def __init__(self, node, cachefile):
        self._downloader = node._client.getServiceNamed("downloader")
        self._uri = node.get_uri()
        self._storage_index = node.get_storage_index()
        self.milestones = set() # of (offset,size,Deferred)
        self.cachefile = cachefile
        self.download_in_progress = False
        # five states:
        #  new FileNode, no downloads ever performed
        #  new FileNode, leftover file (partial)
        #  new FileNode, leftover file (whole)
        #  download in progress, not yet complete
        #  download complete

    def when_range_available(self, offset, size):
        assert isinstance(offset, (int,long))
        assert isinstance(size, (int,long))

        d = defer.Deferred()
        self.milestones.add( (offset,size,d) )
        self._check_milestones()
        if self.milestones and not self.download_in_progress:
            self.download_in_progress = True
            log.msg(format=("immutable filenode read [%(si)s]: " +
                            "starting download"),
                    si=base32.b2a(self._storage_index),
                    umid="h26Heg", level=log.OPERATIONAL)
            d2 = self._downloader.download(self._uri, self)
            d2.addBoth(self._download_done)
            d2.addErrback(self._download_failed)
            d2.addErrback(log.err, umid="cQaM9g")
        return d

    def read(self, consumer, offset, size):
        assert offset+size <= self.get_filesize()
        f = PortionOfFile(self.cachefile.get_filename(), offset, size)
        d = basic.FileSender().beginFileTransfer(f, consumer)
        d.addCallback(lambda lastSent: consumer)
        return d

    def _download_done(self, res):
        # clear download_in_progress, so failed downloads can be re-tried
        self.download_in_progress = False
        return res

    def _download_failed(self, f):
        # tell anyone who's waiting that we failed
        for m in self.milestones:
            (offset,size,d) = m
            eventually(d.errback, f)
        self.milestones.clear()

    def _check_milestones(self):
        current_size = self.get_filesize()
        for m in list(self.milestones):
            (offset,size,d) = m
            if offset+size <= current_size:
                log.msg(format=("immutable filenode read [%(si)s] " +
                                "%(offset)d+%(size)d vs %(filesize)d: " +
                                "done"),
                        si=base32.b2a(self._storage_index),
                        offset=offset, size=size, filesize=current_size,
                        umid="nuedUg", level=log.NOISY)
                self.milestones.discard(m)
                eventually(d.callback, None)
            else:
                log.msg(format=("immutable filenode read [%(si)s] " +
                                "%(offset)d+%(size)d vs %(filesize)d: " +
                                "still waiting"),
                        si=base32.b2a(self._storage_index),
                        offset=offset, size=size, filesize=current_size,
                        umid="8PKOhg", level=log.NOISY)

    def get_filesize(self):
        try:
            filesize = os.stat(self.cachefile.get_filename())[stat.ST_SIZE]
        except OSError:
            filesize = 0
        return filesize


    def open(self, size):
        self.f = open(self.cachefile.get_filename(), "wb")

    def write(self, data):
        self.f.write(data)
        self._check_milestones()

    def close(self):
        self.f.close()
        self._check_milestones()

    def fail(self, why):
        pass
    def register_canceller(self, cb):
        pass
    def finish(self):
        return None



class FileNode(_ImmutableFileNodeBase):
    def __init__(self, uri, client, cachefile):
        _ImmutableFileNodeBase.__init__(self, uri, client)
        self.download_cache = DownloadCache(self, cachefile)

    def get_uri(self):
        return self.u.to_string()

    def get_size(self):
        return self.u.get_size()

    def get_verify_cap(self):
        return self.u.get_verify_cap()

    def get_storage_index(self):
        return self.u.storage_index

    def check_and_repair(self, monitor, verify=False):
        verifycap = self.get_verify_cap()
        servers = self._client.get_servers("storage")

        c = Checker(client=self._client, verifycap=verifycap, servers=servers, verify=verify, monitor=monitor)
        d = c.start()
        def _maybe_repair(cr):
            crr = CheckAndRepairResults(self.u.storage_index)
            crr.pre_repair_results = cr
            if cr.is_healthy():
                crr.post_repair_results = cr
                return defer.succeed(crr)
            else:
                def _gather_repair_results(rr):
                    crr.post_repair_results = rr
                    return crr
                r = Repairer(client=self._client, verifycap=verifycap, servers=servers, monitor=monitor)
                d = r.start()
                d.addCallback(_gather_repair_results)
                return d

        d.addCallback(_maybe_repair)
        return d

    def check(self, monitor, verify=False):
        v = Checker(client=self._client, verifycap=self.get_verify_cap(), servers=self._client.get_servers("storage"), verify=verify, monitor=monitor)
        return v.start()

    def read(self, consumer, offset=0, size=None):
        if size is None:
            size = self.get_size() - offset
        size = min(size, self.get_size() - offset)

        if offset == 0 and size == self.get_size():
            # don't use the cache, just do a normal streaming download
            log.msg(format=("immutable filenode read [%(si)s]: " +
                            "doing normal full download"),
                    si=base32.b2a(self.u.storage_index),
                    umid="VRSBwg", level=log.OPERATIONAL)
            return self.download(download.ConsumerAdapter(consumer))

        d = self.download_cache.when_range_available(offset, size)
        d.addCallback(lambda res:
                      self.download_cache.read(consumer, offset, size))
        return d

    def download(self, target):
        downloader = self._client.getServiceNamed("downloader")
        return downloader.download(self.get_uri(), target)

    def download_to_data(self):
        downloader = self._client.getServiceNamed("downloader")
        return downloader.download_to_data(self.get_uri())

class LiteralProducer:
    implements(IPushProducer)
    def resumeProducing(self):
        pass
    def stopProducing(self):
        pass


class LiteralFileNode(_ImmutableFileNodeBase):

    def __init__(self, uri, client):
        _ImmutableFileNodeBase.__init__(self, uri, client)

    def get_uri(self):
        return self.u.to_string()

    def get_size(self):
        return len(self.u.data)

    def get_verify_cap(self):
        return None

    def get_storage_index(self):
        return None

    def check(self, monitor, verify=False):
        return defer.succeed(None)

    def check_and_repair(self, monitor, verify=False):
        return defer.succeed(None)

    def read(self, consumer, offset=0, size=None):
        if size is None:
            data = self.u.data[offset:]
        else:
            data = self.u.data[offset:offset+size]

        # We use twisted.protocols.basic.FileSender, which only does
        # non-streaming, i.e. PullProducer, where the receiver/consumer must
        # ask explicitly for each chunk of data. There are only two places in
        # the Twisted codebase that can't handle streaming=False, both of
        # which are in the upload path for an FTP/SFTP server
        # (protocols.ftp.FileConsumer and
        # vfs.adapters.ftp._FileToConsumerAdapter), neither of which is
        # likely to be used as the target for a Tahoe download.

        d = basic.FileSender().beginFileTransfer(StringIO(data), consumer)
        d.addCallback(lambda lastSent: consumer)
        return d

    def download(self, target):
        # note that this does not update the stats_provider
        data = self.u.data
        if IConsumer.providedBy(target):
            target.registerProducer(LiteralProducer(), True)
        target.open(len(data))
        target.write(data)
        if IConsumer.providedBy(target):
            target.unregisterProducer()
        target.close()
        return defer.maybeDeferred(target.finish)

    def download_to_data(self):
        data = self.u.data
        return defer.succeed(data)
