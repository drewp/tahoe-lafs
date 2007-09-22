#! /bin/env/python

import os, sys
from twisted.internet import reactor, defer
from twisted.python import log
from twisted.application import service
from foolscap import Tub, eventual

MB = 1000000

class SpeedTest:
    def __init__(self, test_client_dir):
        #self.real_stderr = sys.stderr
        log.startLogging(open("st.log", "a"), setStdout=False)
        f = open(os.path.join(test_client_dir, "control.furl"), "r")
        self.control_furl = f.read().strip()
        f.close()
        self.base_service = service.MultiService()
        self.failed = None
        self.upload_times = {}
        self.download_times = {}

    def run(self):
        print "STARTING"
        d = eventual.fireEventually()
        d.addCallback(lambda res: self.setUp())
        d.addCallback(lambda res: self.do_test())
        d.addBoth(self.tearDown)
        def _err(err):
            self.failed = err
            log.err(err)
            print err
        d.addErrback(_err)
        def _done(res):
            reactor.stop()
            return res
        d.addBoth(_done)
        reactor.run()
        if self.failed:
            print "EXCEPTION"
            print self.failed
            sys.exit(1)

    def setUp(self):
        self.base_service.startService()
        self.tub = Tub()
        self.tub.setServiceParent(self.base_service)
        d = self.tub.getReference(self.control_furl)
        def _gotref(rref):
            self.client_rref = rref
            print "Got Client Control reference"
            return self.stall(5)
        d.addCallback(_gotref)
        return d

    def stall(self, delay, result=None):
        d = defer.Deferred()
        reactor.callLater(delay, d.callback, result)
        return d

    def record_times(self, times, key):
        print "TIME (%s): %s up, %s down" % (key, times[0], times[1])
        self.upload_times[key], self.download_times[key] = times

    def one_test(self, res, name, count, size):
        d = self.client_rref.callRemote("speed_test", count, size)
        d.addCallback(self.record_times, name)
        return d

    def do_test(self):
        print "doing test"
        rr = self.client_rref
        d = defer.succeed(None)
        d.addCallback(self.one_test, "startup", 1, 1000) # ignore this one
        d.addCallback(self.one_test, "1x 200B", 1, 200)
        d.addCallback(self.one_test, "10x 200B", 10, 200)
        #d.addCallback(self.one_test, "100x 200B", 100, 200)
        d.addCallback(self.one_test, "1MB", 1, 1*MB)
        d.addCallback(self.one_test, "10MB", 1, 10*MB)
        def _maybe_do_100MB(res):
            if self.upload_times["10MB"] > 30:
                print "10MB test took too long, skipping 100MB test"
                return
            return self.one_test(None, "100MB", 1, 100*MB)
        d.addCallback(_maybe_do_100MB)
        d.addCallback(self.calculate_speeds)
        return d

    def calculate_speeds(self, res):
        # time = A*size+B
        # we assume that A*200bytes is negligible

        # upload
        B = self.upload_times["10x 200B"] / 10
        print "upload per-file time: %.3fs" % B
        A1 = 1*MB / (self.upload_times["1MB"] - B) # in bytes per second
        print "upload speed (1MB):", self.number(A1, "Bps")
        A2 = 10*MB / (self.upload_times["10MB"] - B)
        print "upload speed (10MB):", self.number(A2, "Bps")
        if "100MB" in self.upload_times:
            A3 = 100*MB / (self.upload_times["100MB"] - B)
            print "upload speed (100MB):", self.number(A3, "Bps")

        # download
        B = self.download_times["10x 200B"] / 10
        print "download per-file time: %.3fs" % B
        A1 = 1*MB / (self.download_times["1MB"] - B) # in bytes per second
        print "download speed (1MB):", self.number(A1, "Bps")
        A2 = 10*MB / (self.download_times["10MB"] - B)
        print "download speed (10MB):", self.number(A2, "Bps")
        if "100MB" in self.download_times:
            A3 = 100*MB / (self.download_times["100MB"] - B)
            print "download speed (100MB):", self.number(A3, "Bps")

    def number(self, value, suffix=""):
        scaling = 1
        if value < 1:
            fmt = "%1.2g%s"
        elif value < 100:
            fmt = "%.1f%s"
        elif value < 1000:
            fmt = "%d%s"
        elif value < 1e6:
            fmt = "%.2fk%s"; scaling = 1e3
        elif value < 1e9:
            fmt = "%.2fM%s"; scaling = 1e6
        elif value < 1e12:
            fmt = "%.2fG%s"; scaling = 1e9
        elif value < 1e15:
            fmt = "%.2fT%s"; scaling = 1e12
        elif value < 1e18:
            fmt = "%.2fP%s"; scaling = 1e15
        else:
            fmt = "huge! %g%s"
        return fmt % (value / scaling, suffix)

    def tearDown(self, res):
        d = self.base_service.stopService()
        d.addCallback(lambda ignored: res)
        return d


if __name__ == '__main__':
    test_client_dir = sys.argv[1]
    st = SpeedTest(test_client_dir)
    st.run()
