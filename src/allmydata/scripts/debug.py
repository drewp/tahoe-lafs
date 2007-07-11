
import os, sys
from twisted.python import usage
from allmydata.scripts.common import BasedirMixin

class DumpOptions(usage.Options):
    optParameters = [
        ["filename", "f", None, "which file to dump"],
        ]

    def parseArgs(self, filename=None):
        if filename:
            self['filename'] = filename

    def postOptions(self):
        if not self['filename']:
            raise usage.UsageError("<filename> parameter is required")

class DumpRootDirnodeOptions(BasedirMixin, usage.Options):
    optParameters = [
        ["basedir", "C", None, "the vdrive-server's base directory"],
        ]

class DumpDirnodeOptions(BasedirMixin, usage.Options):
    optParameters = [
        ["uri", "u", None, "the URI of the dirnode to dump."],
        ["basedir", "C", None, "which directory to create the introducer in"],
        ]
    optFlags = [
        ["verbose", "v", "be extra noisy (show encrypted data)"],
        ]
    def parseArgs(self, *args):
        if len(args) == 1:
            self['uri'] = args[-1]
            args = args[:-1]
        BasedirMixin.parseArgs(self, *args)

    def postOptions(self):
        BasedirMixin.postOptions(self)
        if not self['uri']:
            raise usage.UsageError("<uri> parameter is required")

def dump_uri_extension(config, out=sys.stdout, err=sys.stderr):
    from allmydata import uri

    filename = config['filename']
    unpacked = uri.unpack_extension_readable(open(filename,"rb").read())
    keys1 = ("size", "num_segments", "segment_size",
             "needed_shares", "total_shares")
    keys2 = ("codec_name", "codec_params", "tail_codec_params")
    keys3 = ("plaintext_hash", "plaintext_root_hash",
             "crypttext_hash", "crypttext_root_hash",
             "share_root_hash")
    for k in keys1:
        if k in unpacked:
            print >>out, "%19s: %s" % (k, unpacked[k])
    print >>out
    for k in keys2:
        if k in unpacked:
            print >>out, "%19s: %s" % (k, unpacked[k])
    print >>out
    for k in keys3:
        if k in unpacked:
            print >>out, "%19s: %s" % (k, unpacked[k])

    leftover = set(unpacked.keys()) - set(keys1 + keys2 + keys3)
    if leftover:
        print >>out
        for k in sorted(leftover):
            print >>out, "%s: %s" % (k, unpacked[k])

    print >>out
    return 0

def dump_root_dirnode(config, out=sys.stdout, err=sys.stderr):
    from allmydata import uri

    basedir = config['basedirs'][0]
    root_dirnode_file = os.path.join(basedir, "vdrive", "root")
    try:
        f = open(root_dirnode_file, "rb")
        key = f.read()
        rooturi = uri.pack_dirnode_uri("fakeFURL", key)
        print >>out, rooturi
        return 0
    except EnvironmentError:
        print >>out,  "unable to read root dirnode file from %s" % \
              root_dirnode_file
        return 1

def dump_directory_node(config, out=sys.stdout, err=sys.stderr):
    from allmydata import uri, dirnode
    from allmydata.util import hashutil, idlib
    basedir = config['basedirs'][0]
    dir_uri = config['uri']
    verbose = config['verbose']

    furl, key = uri.unpack_dirnode_uri(dir_uri)
    if uri.is_mutable_dirnode_uri(dir_uri):
        wk, we, rk, index = hashutil.generate_dirnode_keys_from_writekey(key)
    else:
        wk, we, rk, index = hashutil.generate_dirnode_keys_from_readkey(key)

    filename = os.path.join(basedir, "vdrive", idlib.b2a(index))

    print >>out
    print >>out, "dirnode uri: %s" % dir_uri
    print >>out, "filename : %s" % filename
    print >>out, "index        : %s" % idlib.b2a(index)
    if wk:
        print >>out, "writekey     : %s" % idlib.b2a(wk)
        print >>out, "write_enabler: %s" % idlib.b2a(we)
    else:
        print >>out, "writekey     : None"
        print >>out, "write_enabler: None"
    print >>out, "readkey      : %s" % idlib.b2a(rk)

    print >>out

    vds = dirnode.VirtualDriveServer(os.path.join(basedir, "vdrive"), False)
    data = vds._read_from_file(index)
    if we:
        if we != data[0]:
            print >>out, "ERROR: write_enabler does not match"

    for (H_key, E_key, E_write, E_read) in data[1]:
        if verbose:
            print >>out, " H_key %s" % idlib.b2a(H_key)
            print >>out, " E_key %s" % idlib.b2a(E_key)
            print >>out, " E_write %s" % idlib.b2a(E_write)
            print >>out, " E_read %s" % idlib.b2a(E_read)
        key = dirnode.decrypt(rk, E_key)
        print >>out, " key %s" % key
        if hashutil.dir_name_hash(rk, key) != H_key:
            print >>out, "  ERROR: H_key does not match"
        if wk and E_write:
            if len(E_write) < 14:
                print >>out, "  ERROR: write data is short:", idlib.b2a(E_write)
            write = dirnode.decrypt(wk, E_write)
            print >>out, "   write: %s" % write
        read = dirnode.decrypt(rk, E_read)
        print >>out, "   read: %s" % read
        print >>out

    return 0


subCommands = [
    ["dump-uri-extension", None, DumpOptions,
     "Unpack and display the contents of a uri_extension file."],
    ["dump-root-dirnode", None, DumpRootDirnodeOptions,
     "Compute most of the URI for the vdrive server's root dirnode."],
    ["dump-dirnode", None, DumpDirnodeOptions,
     "Unpack and display the contents of a vdrive DirectoryNode."],
    ]

dispatch = {
    "dump-uri-extension": dump_uri_extension,
    "dump-root-dirnode": dump_root_dirnode,
    "dump-dirnode": dump_directory_node,
    }
