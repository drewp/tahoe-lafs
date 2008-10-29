
import os, time
from zope.interface import implements
from twisted.application import service
from twisted.internet import defer
from foolscap import Referenceable
from allmydata.interfaces import RIControlClient
from allmydata.util import fileutil, mathutil
from allmydata.immutable import upload, download
from twisted.python import log

def get_memory_usage():
    # this is obviously linux-specific
    stat_names = ("VmPeak",
                  "VmSize",
                  #"VmHWM",
                  "VmData")
    stats = {}
    try:
        for line in open("/proc/self/status", "r").readlines():
            name, right = line.split(":",2)
            if name in stat_names:
                assert right.endswith(" kB\n")
                right = right[:-4]
                stats[name] = int(right) * 1024
    except:
        # Probably not on (a compatible version of) Linux
        stats['VmSize'] = 0
        stats['VmPeak'] = 0
    return stats

def log_memory_usage(where=""):
    stats = get_memory_usage()
    log.msg("VmSize: %9d  VmPeak: %9d  %s" % (stats["VmSize"],
                                              stats["VmPeak"],
                                              where))


class ControlServer(Referenceable, service.Service):
    implements(RIControlClient)

    def remote_wait_for_client_connections(self, num_clients):
        return self.parent.debug_wait_for_client_connections(num_clients)

    def remote_upload_from_file_to_uri(self, filename, convergence):
        uploader = self.parent.getServiceNamed("uploader")
        u = upload.FileName(filename, convergence=convergence)
        d = uploader.upload(u)
        d.addCallback(lambda results: results.uri)
        return d

    def remote_download_from_uri_to_file(self, uri, filename):
        downloader = self.parent.getServiceNamed("downloader")
        d = downloader.download_to_filename(uri, filename)
        d.addCallback(lambda res: filename)
        return d

    def remote_speed_test(self, count, size, mutable):
        assert size > 8
        log.msg("speed_test: count=%d, size=%d, mutable=%s" % (count, size,
                                                               mutable))
        st = SpeedTest(self.parent, count, size, mutable)
        return st.run()

    def remote_get_memory_usage(self):
        return get_memory_usage()

    def remote_measure_peer_response_time(self):
        # I'd like to average together several pings, but I don't want this
        # phase to take more than 10 seconds. Expect worst-case latency to be
        # 300ms.
        results = {}
        conns = self.parent.introducer_client.get_all_connections_for("storage")
        everyone = [(peerid,rref) for (peerid, service_name, rref) in conns]
        num_pings = int(mathutil.div_ceil(10, (len(everyone) * 0.3)))
        everyone = everyone * num_pings
        d = self._do_one_ping(None, everyone, results)
        return d
    def _do_one_ping(self, res, everyone_left, results):
        if not everyone_left:
            return results
        peerid, connection = everyone_left.pop(0)
        start = time.time()
        d = connection.callRemote("get_versions")
        def _done(ignored):
            stop = time.time()
            elapsed = stop - start
            if peerid in results:
                results[peerid].append(elapsed)
            else:
                results[peerid] = [elapsed]
        d.addCallback(_done)
        d.addCallback(self._do_one_ping, everyone_left, results)
        def _average(res):
            averaged = {}
            for peerid,times in results.iteritems():
                averaged[peerid] = sum(times) / len(times)
            return averaged
        d.addCallback(_average)
        return d

class SpeedTest:
    def __init__(self, parent, count, size, mutable):
        self.parent = parent
        self.count = count
        self.size = size
        self.mutable_mode = mutable
        self.uris = {}
        self.basedir = os.path.join(self.parent.basedir, "_speed_test_data")

    def run(self):
        self.create_data()
        d = self.do_upload()
        d.addCallback(lambda res: self.do_download())
        d.addBoth(self.do_cleanup)
        d.addCallback(lambda res: (self.upload_time, self.download_time))
        return d

    def create_data(self):
        fileutil.make_dirs(self.basedir)
        for i in range(self.count):
            s = self.size
            fn = os.path.join(self.basedir, str(i))
            if os.path.exists(fn):
                os.unlink(fn)
            f = open(fn, "w")
            f.write(os.urandom(8))
            s -= 8
            while s > 0:
                chunk = min(s, 4096)
                f.write("\x00" * chunk)
                s -= chunk
            f.close()

    def do_upload(self):
        d = defer.succeed(None)
        def _create_slot(res):
            d1 = self.parent.create_mutable_file("")
            def _created(n):
                self._n = n
            d1.addCallback(_created)
            return d1
        if self.mutable_mode == "upload":
            d.addCallback(_create_slot)
        def _start(res):
            self._start = time.time()
        d.addCallback(_start)

        def _record_uri(uri, i):
            self.uris[i] = uri
        def _upload_one_file(ignored, i):
            if i >= self.count:
                return
            fn = os.path.join(self.basedir, str(i))
            if self.mutable_mode == "create":
                data = open(fn,"rb").read()
                d1 = self.parent.create_mutable_file(data)
                d1.addCallback(lambda n: n.get_uri())
            elif self.mutable_mode == "upload":
                data = open(fn,"rb").read()
                d1 = self._n.overwrite(data)
                d1.addCallback(lambda res: self._n.get_uri())
            else:
                up = upload.FileName(fn, convergence=None)
                d1 = self.parent.upload(up)
                d1.addCallback(lambda results: results.uri)
            d1.addCallback(_record_uri, i)
            d1.addCallback(_upload_one_file, i+1)
            return d1
        d.addCallback(_upload_one_file, 0)
        def _upload_done(ignored):
            stop = time.time()
            self.upload_time = stop - self._start
        d.addCallback(_upload_done)
        return d

    def do_download(self):
        start = time.time()
        d = defer.succeed(None)
        def _download_one_file(ignored, i):
            if i >= self.count:
                return
            n = self.parent.create_node_from_uri(self.uris[i])
            d1 = n.download(download.FileHandle(Discard()))
            d1.addCallback(_download_one_file, i+1)
            return d1
        d.addCallback(_download_one_file, 0)
        def _download_done(ignored):
            stop = time.time()
            self.download_time = stop - start
        d.addCallback(_download_done)
        return d

    def do_cleanup(self, res):
        for i in range(self.count):
            fn = os.path.join(self.basedir, str(i))
            os.unlink(fn)
        return res

class Discard:
    def write(self, data):
        pass
    # download_to_filehandle explicitly does not close the filehandle it was
    # given: that is reserved for the provider of the filehandle. Therefore
    # the lack of a close() method on this otherwise filehandle-like object
    # is a part of the test.
