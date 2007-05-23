
import os, sha
from foolscap import Referenceable
from zope.interface import implements
from allmydata.interfaces import RIClient
from allmydata import node

from twisted.internet import defer

import allmydata
from allmydata.Crypto.Util.number import bytes_to_long
from allmydata.storageserver import StorageServer
from allmydata.upload import Uploader
from allmydata.download import Downloader
from allmydata.vdrive import VDrive
from allmydata.webish import WebishServer
from allmydata.control import ControlServer
from allmydata.introducer import IntroducerClient

class Client(node.Node, Referenceable):
    implements(RIClient)
    PORTNUMFILE = "client.port"
    STOREDIR = 'storage'
    NODETYPE = "client"
    WEBPORTFILE = "webport"
    INTRODUCER_FURL_FILE = "introducer.furl"
    GLOBAL_VDRIVE_FURL_FILE = "vdrive.furl"

    # we're pretty narrow-minded right now
    OLDEST_SUPPORTED_VERSION = allmydata.__version__

    def __init__(self, basedir="."):
        node.Node.__init__(self, basedir)
        self.my_furl = None
        self.introducer_client = None
        self.connected_to_vdrive = False
        self.add_service(StorageServer(os.path.join(basedir, self.STOREDIR)))
        self.add_service(Uploader())
        self.add_service(Downloader())
        self.add_service(VDrive())
        WEBPORTFILE = os.path.join(self.basedir, self.WEBPORTFILE)
        if os.path.exists(WEBPORTFILE):
            f = open(WEBPORTFILE, "r")
            webport = f.read() # strports string
            f.close()
            self.add_service(WebishServer(webport))

        INTRODUCER_FURL_FILE = os.path.join(self.basedir,
                                            self.INTRODUCER_FURL_FILE)
        f = open(INTRODUCER_FURL_FILE, "r")
        self.introducer_furl = f.read().strip()
        f.close()

        GLOBAL_VDRIVE_FURL_FILE = os.path.join(self.basedir,
                                               self.GLOBAL_VDRIVE_FURL_FILE)
        f = open(GLOBAL_VDRIVE_FURL_FILE, "r")
        self.global_vdrive_furl = f.read().strip()
        f.close()

    def tub_ready(self):
        self.log("tub_ready")
        self.my_furl = self.tub.registerReference(self)

        ic = IntroducerClient(self.tub, self.introducer_furl, self.my_furl)
        self.introducer_client = ic
        ic.setServiceParent(self)

        self.register_control()

        self.vdrive_connector = self.tub.connectTo(self.global_vdrive_furl,
                                                   self._got_vdrive)

    def register_control(self):
        c = ControlServer()
        c.setServiceParent(self)
        control_url = self.tub.registerReference(c)
        f = open("control.furl", "w")
        f.write(control_url + "\n")
        f.close()
        os.chmod("control.furl", 0600)

    def _got_vdrive(self, vdrive_root):
        # vdrive_root implements RIMutableDirectoryNode
        self.log("connected to vdrive")
        self.connected_to_vdrive = True
        self.getServiceNamed("vdrive").set_root(vdrive_root)
        if "webish" in self.namedServices:
            self.getServiceNamed("webish").set_root_dirnode(vdrive_root)
        def _disconnected():
            self.connected_to_vdrive = False
        vdrive_root.notifyOnDisconnect(_disconnected)

    def remote_get_versions(self):
        return str(allmydata.__version__), str(self.OLDEST_SUPPORTED_VERSION)

    def remote_get_service(self, name):
        # TODO: 'vdrive' should not be public in the medium term
        return self.getServiceNamed(name)

    def get_remote_service(self, nodeid, servicename):
        if nodeid not in self.introducer_client.connections:
            return defer.fail(IndexError("no connection to that peer"))
        peer = self.introducer_client.connections[nodeid]
        d = peer.callRemote("get_service", name=servicename)
        return d


    def get_all_peerids(self):
        return self.introducer_client.connections.iterkeys()

    def get_permuted_peers(self, key):
        """
        @return: list of (permuted-peerid, peerid, connection,)
        """
        results = []
        for peerid, connection in self.introducer_client.connections.iteritems():
            assert isinstance(peerid, str)
            permuted = bytes_to_long(sha.new(key + peerid).digest())
            results.append((permuted, peerid, connection))
        results.sort()
        return results
