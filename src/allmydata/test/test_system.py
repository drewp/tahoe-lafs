
from twisted.trial import unittest
from twisted.internet import defer, reactor
from twisted.application import service
from allmydata import client, queen
import os
from foolscap.eventual import flushEventualQueue
from twisted.python import log
from twisted.web.client import getPage

class SystemTest(unittest.TestCase):
    # it takes a little while for a disconnected loopback TCP connection to
    # be noticed by the other side. This is not directly visible to us, so we
    # have to wait for time to pass rather than just waiting on a deferred.
    # This is unfortunate, both because it arbitrarily slows down the test
    # process, and because it is hard to predict what the minimum time
    # necessary would be (on a slow or heavily loaded system, 100ms might not
    # be enough).
    DISCONNECT_DELAY = 0.1

    def setUp(self):
        self.sparent = service.MultiService()
        self.sparent.startService()
    def tearDown(self):
        log.msg("shutting down SystemTest services")
        d = self.sparent.stopService()
        d.addCallback(lambda res: flushEventualQueue())
        def _done(res):
            d1 = defer.Deferred()
            reactor.callLater(self.DISCONNECT_DELAY, d1.callback, None)
            return d1
        d.addCallback(_done)
        return d

    def add_service(self, s):
        s.setServiceParent(self.sparent)
        return s

    def set_up_nodes(self, NUMCLIENTS=5):
        self.numclients = NUMCLIENTS
        if not os.path.isdir("queen"):
            os.mkdir("queen")
        self.queen = self.add_service(queen.Queen(basedir="queen"))
        d = self.queen.when_tub_ready()
        d.addCallback(self._set_up_nodes_2)
        return d

    def _set_up_nodes_2(self, res):
        q = self.queen
        self.queen_furl = q.urls["introducer"]
        self.vdrive_furl = q.urls["vdrive"]
        self.clients = []
        for i in range(self.numclients):
            basedir = "client%d" % i
            if not os.path.isdir(basedir):
                os.mkdir(basedir)
            if i == 0:
                open(os.path.join(basedir, "webport"), "w").write("tcp:0:interface=127.0.0.1")
            open(os.path.join(basedir, "introducer.furl"), "w").write(self.queen_furl)
            open(os.path.join(basedir, "vdrive.furl"), "w").write(self.vdrive_furl)
            c = self.add_service(client.Client(basedir=basedir))
            self.clients.append(c)
        log.msg("STARTING")
        d = self.wait_for_connections()
        def _connected(res):
            # now find out where the web port was
            l = self.clients[0].getServiceNamed("webish").listener
            port = l._port.getHost().port
            self.webish_url = "http://localhost:%d/" % port
        d.addCallback(_connected)
        return d

    def add_extra_node(self, client_num):
        # this node is *not* parented to our self.sparent, so we can shut it
        # down separately from the rest, to exercise the connection-lost code
        basedir = "client%d" % client_num
        if not os.path.isdir(basedir):
            os.mkdir(basedir)
        open(os.path.join(basedir, "introducer.furl"), "w").write(self.queen_furl)
        open(os.path.join(basedir, "vdrive.furl"), "w").write(self.vdrive_furl)

        c = client.Client(basedir=basedir)
        self.clients.append(c)
        self.numclients += 1
        c.startService()
        d = self.wait_for_connections()
        d.addCallback(lambda res: c)
        return d

    def wait_for_connections(self, ignored=None):
        for c in self.clients:
            if (not c.introducer_client or
                len(list(c.get_all_peerids())) != self.numclients):
                d = defer.Deferred()
                d.addCallback(self.wait_for_connections)
                reactor.callLater(0.05, d.callback, None)
                return d
        return defer.succeed(None)

    def test_connections(self):
        d = self.set_up_nodes()
        self.extra_node = None
        d.addCallback(lambda res: self.add_extra_node(5))
        def _check(extra_node):
            self.extra_node = extra_node
            for c in self.clients:
                self.failUnlessEqual(len(list(c.get_all_peerids())), 6)
        d.addCallback(_check)
        def _shutdown_extra_node(res):
            if self.extra_node:
                d1 = self.extra_node.stopService()
                d2 = defer.Deferred()
                reactor.callLater(self.DISCONNECT_DELAY, d2.callback, res)
                d1.addCallback(lambda ignored: d2)
                return d1
            return res
        d.addBoth(_shutdown_extra_node)
        return d

    def test_upload_and_download(self):
        DATA = "Some data to upload\n"
        d = self.set_up_nodes()
        def _do_upload(res):
            log.msg("UPLOADING")
            u = self.clients[0].getServiceNamed("uploader")
            d1 = u.upload_data(DATA)
            return d1
        d.addCallback(_do_upload)
        def _upload_done(uri):
            log.msg("upload finished: uri is %s" % (uri,))
            dl = self.clients[1].getServiceNamed("downloader")
            d1 = dl.download_to_data(uri)
            return d1
        d.addCallback(_upload_done)
        def _download_done(data):
            log.msg("download finished")
            self.failUnlessEqual(data, DATA)
        d.addCallback(_download_done)
        return d

    def test_vdrive(self):
        self.data = DATA = "Some data to publish to the virtual drive\n"
        d = self.set_up_nodes()
        def _do_publish(res):
            log.msg("PUBLISHING")
            v0 = self.clients[0].getServiceNamed("vdrive")
            d1 = v0.make_directory("/", "subdir1")
            d1.addCallback(lambda subdir1:
                           v0.put_file_by_data(subdir1, "mydata567", DATA))
            return d1
        d.addCallback(_do_publish)
        def _publish_done(res):
            log.msg("publish finished")
            v1 = self.clients[1].getServiceNamed("vdrive")
            d1 = v1.get_file_to_data("/subdir1/mydata567")
            return d1
        d.addCallback(_publish_done)
        def _get_done(data):
            log.msg("get finished")
            self.failUnlessEqual(data, DATA)
        d.addCallback(_get_done)
        d.addCallback(self._test_web)
        return d

    def _test_web(self, res):
        base = self.webish_url
        d = getPage(base)
        def _got_welcome(page):
            expected = "Connected Peers: <span>%d</span>" % (self.numclients)
            self.failUnless(expected in page,
                            "I didn't see the right 'connected peers' message "
                            "in: %s" % page
                            )
        d.addCallback(_got_welcome)
        d.addCallback(lambda res: getPage(base + "vdrive/subdir1"))
        def _got_subdir1(page):
            # there ought to be an href for our file
            self.failUnless(">mydata567</a>" in page)
        d.addCallback(_got_subdir1)
        d.addCallback(lambda res: getPage(base + "vdrive/subdir1/mydata567"))
        def _got_data(page):
            self.failUnlessEqual(page, self.data)
        d.addCallback(_got_data)
        return d

