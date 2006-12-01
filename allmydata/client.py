
import os.path
from foolscap import Tub, Referenceable
from twisted.application import service
from twisted.python import log
from allmydata.util.iputil import get_local_ip_for

from twisted.internet import reactor
from twisted.internet.base import BlockingResolver
reactor.installResolver(BlockingResolver())

class Storage(service.MultiService, Referenceable):
    name = "storage"
    pass

class Client(service.MultiService, Referenceable):
    CERTFILE = "client.pem"
    AUTHKEYSFILE = "authorized_keys"

    def __init__(self, queen_pburl):
        service.MultiService.__init__(self)
        self.queen_pburl = queen_pburl
        if os.path.exists(self.CERTFILE):
            self.tub = Tub(certData=open(self.CERTFILE, "rb").read())
        else:
            self.tub = Tub()
            f = open(self.CERTFILE, "wb")
            f.write(self.tub.getCertData())
            f.close()
        self.tub.setServiceParent(self)
        self.queen = None # self.queen is either None or a RemoteReference
        self.all_peers = set()
        self.connections = {}
        s = Storage()
        s.setServiceParent(self)

        if os.path.exists(self.AUTHKEYSFILE):
            from allmydata import manhole
            m = manhole.AuthorizedKeysManhole(8022, self.AUTHKEYSFILE)
            m.setServiceParent(self)
            log.msg("AuthorizedKeysManhole listening on 8022")

    def _setup_tub(self, local_ip):
        portnum = 0
        l = self.tub.listenOn("tcp:%d" % portnum)
        self.tub.setLocation("%s:%d" % (local_ip, l.getPortnum()))
        self.my_pburl = self.tub.registerReference(self)

    def startService(self):
        # note: this class can only be started and stopped once.
        service.MultiService.startService(self)
        d = get_local_ip_for()
        d.addCallback(self._setup_tub)
        if self.queen_pburl:
            # TODO: maybe this should wait for tub.setLocation ?
            self.connector = self.tub.connectTo(self.queen_pburl,
                                                self._got_queen)
        else:
            log.msg("no queen_pburl, cannot connect")

    def stopService(self):
        if self.queen_pburl:
            self.connector.stopConnecting()
        service.MultiService.stopService(self)

    def _got_queen(self, queen):
        log.msg("connected to queen")
        self.queen = queen
        queen.notifyOnDisconnect(self._lost_queen)
        queen.callRemote("hello",
                         nodeid=self.tub.tubID, node=self, pburl=self.my_pburl)

    def _lost_queen(self):
        log.msg("lost connection to queen")
        self.queen = None

    def remote_get_service(self, name):
        return self.getServiceNamed(name)

    def remote_add_peers(self, new_peers):
        for nodeid, pburl in new_peers:
            if nodeid == self.tub.tubID:
                continue
            log.msg("adding peer %s" % nodeid)
            if nodeid in self.all_peers:
                log.msg("weird, I already had an entry for them")
            self.all_peers.add(nodeid)
            if nodeid not in self.connections:
                d = self.tub.getReference(pburl)
                def _got_reference(ref):
                    log.msg("connected to %s" % nodeid)
                    if nodeid in self.all_peers:
                        self.connections[nodeid] = ref
                d.addCallback(_got_reference)

    def remote_lost_peers(self, lost_peers):
        for nodeid in lost_peers:
            log.msg("lost peer %s" % nodeid)
            if nodeid in self.all_peers:
                self.all_peers.remove(nodeid)
            else:
                log.msg("weird, I didn't have an entry for them")
            if nodeid in self.connections:
                del self.connections[nodeid]

    def get_remote_service(self, nodeid, servicename):
        if nodeid not in self.connections:
            raise IndexError("no connection to that peer")
        d = self.connections[nodeid].callRemote("get_service", name=servicename)
        return d
