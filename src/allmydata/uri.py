
import re
from allmydata.util import idlib, hashutil

# the URI shall be an ascii representation of the file. It shall contain
# enough information to retrieve and validate the contents. It shall be
# expressed in a limited character set (namely [TODO]).

def pack_uri(storage_index, key, uri_extension_hash,
             needed_shares, total_shares, size):
    # applications should pass keyword parameters into this
    assert isinstance(storage_index, str)
    assert len(storage_index) == 32 # sha256 hash

    assert isinstance(uri_extension_hash, str)
    assert len(uri_extension_hash) == 32 # sha56 hash

    assert isinstance(key, str)
    assert len(key) == 16 # AES-128
    assert isinstance(needed_shares, int)
    assert isinstance(total_shares, int)
    assert isinstance(size, (int,long))

    return "URI:%s:%s:%s:%d:%d:%d" % (idlib.b2a(storage_index), idlib.b2a(key),
                                      idlib.b2a(uri_extension_hash),
                                      needed_shares, total_shares, size)


def unpack_uri(uri):
    assert uri.startswith("URI:")
    d = {}
    (header,
     storage_index_s, key_s, uri_extension_hash_s,
     needed_shares_s, total_shares_s, size_s) = uri.split(":")
    assert header == "URI"
    d['storage_index'] = idlib.a2b(storage_index_s)
    d['key'] = idlib.a2b(key_s)
    d['uri_extension_hash'] = idlib.a2b(uri_extension_hash_s)
    d['needed_shares'] = int(needed_shares_s)
    d['total_shares'] = int(total_shares_s)
    d['size'] = int(size_s)
    return d


def pack_extension(data):
    pieces = []
    for k in sorted(data.keys()):
        value = data[k]
        if isinstance(value, (int, long)):
            value = "%d" % value
        assert isinstance(value, str), k
        assert re.match(r'^[a-zA-Z_\-]+$', k)
        pieces.append(k + ":" + hashutil.netstring(value))
    uri_extension = "".join(pieces)
    return uri_extension

def unpack_extension(data):
    d = {}
    while data:
        colon = data.index(":")
        key = data[:colon]
        data = data[colon+1:]

        colon = data.index(":")
        number = data[:colon]
        length = int(number)
        data = data[colon+1:]

        value = data[:length]
        assert data[length] == ","
        data = data[length+1:]

        d[key] = value

    # convert certain things to numbers
    for intkey in ("size", "segment_size", "num_segments",
                   "needed_shares", "total_shares"):
        if intkey in d:
            d[intkey] = int(d[intkey])
    return d

