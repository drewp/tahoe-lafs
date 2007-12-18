
from twisted.trial import unittest
from allmydata import uri
from allmydata.util import hashutil
from allmydata.interfaces import IURI, IFileURI, IDirnodeURI, IMutableFileURI, \
    IVerifierURI
from foolscap.schema import Violation

class Literal(unittest.TestCase):
    def _help_test(self, data):
        u = uri.LiteralFileURI(data)
        self.failUnless(IURI.providedBy(u))
        self.failUnless(IFileURI.providedBy(u))
        self.failIf(IDirnodeURI.providedBy(u))
        self.failUnlessEqual(u.data, data)
        self.failUnlessEqual(u.get_size(), len(data))
        self.failUnless(u.is_readonly())
        self.failIf(u.is_mutable())

        u2 = uri.from_string(u.to_string())
        self.failUnless(IURI.providedBy(u2))
        self.failUnless(IFileURI.providedBy(u2))
        self.failIf(IDirnodeURI.providedBy(u2))
        self.failUnlessEqual(u2.data, data)
        self.failUnlessEqual(u2.get_size(), len(data))
        self.failUnless(u.is_readonly())
        self.failIf(u.is_mutable())

        u3 = u.get_readonly()
        self.failUnlessIdentical(u, u3)
        self.failUnlessEqual(u.get_verifier(), None)

    def test_empty(self):
        data = "" # This data is some *very* small data!
        return self._help_test(data)

    def test_pack(self):
        data = "This is some small data"
        return self._help_test(data)

    def test_nonascii(self):
        data = "This contains \x00 and URI:LIT: and \n, oh my."
        return self._help_test(data)

class Compare(unittest.TestCase):
    def test_compare(self):
        lit1 = uri.LiteralFileURI("some data")
        fileURI = 'URI:CHK:f3mf6az85wpcai8ma4qayfmxuc:nnw518w5hu3t5oohwtp7ah9n81z9rfg6c1ywk33ia3m64o67nsgo:3:10:345834'
        chk1 = uri.CHKFileURI().init_from_string(fileURI)
        chk2 = uri.CHKFileURI().init_from_string(fileURI)
        self.failIfEqual(lit1, chk1)
        self.failUnlessEqual(chk1, chk2)
        self.failIfEqual(chk1, "not actually a URI")
        # these should be hashable too
        s = set([lit1, chk1, chk2])
        self.failUnlessEqual(len(s), 2) # since chk1==chk2

class CHKFile(unittest.TestCase):
    def test_pack(self):
        key = "\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f"
        storage_index = hashutil.storage_index_chk_hash(key)
        uri_extension_hash = hashutil.uri_extension_hash("stuff")
        needed_shares = 25
        total_shares = 100
        size = 1234
        u = uri.CHKFileURI(key=key,
                           uri_extension_hash=uri_extension_hash,
                           needed_shares=needed_shares,
                           total_shares=total_shares,
                           size=size)
        self.failUnlessEqual(u.storage_index, storage_index)
        self.failUnlessEqual(u.key, key)
        self.failUnlessEqual(u.uri_extension_hash, uri_extension_hash)
        self.failUnlessEqual(u.needed_shares, needed_shares)
        self.failUnlessEqual(u.total_shares, total_shares)
        self.failUnlessEqual(u.size, size)
        self.failUnless(u.is_readonly())
        self.failIf(u.is_mutable())
        self.failUnless(IURI.providedBy(u))
        self.failUnless(IFileURI.providedBy(u))
        self.failIf(IDirnodeURI.providedBy(u))
        self.failUnlessEqual(u.get_size(), 1234)
        self.failUnless(u.is_readonly())
        self.failIf(u.is_mutable())
        u_ro = u.get_readonly()
        self.failUnlessIdentical(u, u_ro)
        u1a = IFileURI(u.to_string())
        self.failUnlessEqual(u1a, u)

        u2 = uri.from_string(u.to_string())
        self.failUnlessEqual(u2.storage_index, storage_index)
        self.failUnlessEqual(u2.key, key)
        self.failUnlessEqual(u2.uri_extension_hash, uri_extension_hash)
        self.failUnlessEqual(u2.needed_shares, needed_shares)
        self.failUnlessEqual(u2.total_shares, total_shares)
        self.failUnlessEqual(u2.size, size)
        self.failUnless(u2.is_readonly())
        self.failIf(u2.is_mutable())
        self.failUnless(IURI.providedBy(u2))
        self.failUnless(IFileURI.providedBy(u2))
        self.failIf(IDirnodeURI.providedBy(u2))
        self.failUnlessEqual(u2.get_size(), 1234)
        self.failUnless(u2.is_readonly())
        self.failIf(u2.is_mutable())

        v = u.get_verifier()
        self.failUnless(isinstance(v.to_string(), str))
        v2 = uri.from_string(v.to_string())
        self.failUnlessEqual(v, v2)

        v3 = uri.CHKFileVerifierURI(storage_index="\x00"*16,
                                    uri_extension_hash="\x00"*32,
                                    needed_shares=3,
                                    total_shares=10,
                                    size=1234)
        self.failUnless(isinstance(v3.to_string(), str))

    def test_pack_badly(self):
        key = "\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f"
        storage_index = hashutil.storage_index_chk_hash(key)
        uri_extension_hash = hashutil.uri_extension_hash("stuff")
        needed_shares = 25
        total_shares = 100
        size = 1234
        self.failUnlessRaises(TypeError,
                              uri.CHKFileURI,
                              key=key,
                              uri_extension_hash=uri_extension_hash,
                              needed_shares=needed_shares,
                              total_shares=total_shares,
                              size=size,

                              bogus_extra_argument="reject me",
                              )
        self.failUnlessRaises(TypeError,
                              uri.CHKFileVerifierURI,
                              bogus="bogus")
        self.failUnlessRaises(TypeError,
                              uri.CHKFileVerifierURI,
                              storage_index=storage_index,
                              uri_extension_hash=uri_extension_hash,
                              needed_shares=3,
                              total_shares=10,
                              # leave size= missing
                              )


class Extension(unittest.TestCase):
    def test_pack(self):
        data = {"stuff": "value",
                "size": 12,
                "needed_shares": 3,
                "big_hash": hashutil.tagged_hash("foo", "bar"),
                }
        ext = uri.pack_extension(data)
        d = uri.unpack_extension(ext)
        self.failUnlessEqual(d["stuff"], "value")
        self.failUnlessEqual(d["size"], 12)
        self.failUnlessEqual(d["big_hash"], hashutil.tagged_hash("foo", "bar"))

        readable = uri.unpack_extension_readable(ext)

class Invalid(unittest.TestCase):
    def test_create_invalid(self):
        not_uri = "I am not a URI"
        self.failUnlessRaises(TypeError, uri.from_string, not_uri)


class Constraint(unittest.TestCase):
    def test_constraint(self):
       good="http://127.0.0.1:8123/uri/URI%3ADIR2%3Aqo8ayna47cpw3rx3kho3mu7q4h%3Abk9qbgx76gh6eyj5ps8p6buz8fffw1ofc37e9w9d6ncsfpuz7icy/"
       self.failUnless(uri.DirnodeURI_RE.search(good))
       bad = good + '==='
       self.failIf(uri.DirnodeURI_RE.search(bad))
       fileURI = 'URI:CHK:f3mf6az85wpcai8ma4qayfmxuc:nnw518w5hu3t5oohwtp7ah9n81z9rfg6c1ywk33ia3m64o67nsgo:3:10:345834'
       self.failIf(uri.DirnodeURI_RE.search(fileURI))


class Mutable(unittest.TestCase):
    def test_pack(self):
        writekey = "\x01" * 16
        fingerprint = "\x02" * 32

        u = uri.WriteableSSKFileURI(writekey, fingerprint)
        self.failUnlessEqual(u.writekey, writekey)
        self.failUnlessEqual(u.fingerprint, fingerprint)
        self.failIf(u.is_readonly())
        self.failUnless(u.is_mutable())
        self.failUnless(IURI.providedBy(u))
        self.failUnless(IMutableFileURI.providedBy(u))
        self.failIf(IDirnodeURI.providedBy(u))
        self.failUnless("WriteableSSKFileURI" in str(u))
        u1a = IMutableFileURI(u.to_string())
        self.failUnlessEqual(u1a, u)

        u2 = uri.from_string(u.to_string())
        self.failUnlessEqual(u2.writekey, writekey)
        self.failUnlessEqual(u2.fingerprint, fingerprint)
        self.failIf(u2.is_readonly())
        self.failUnless(u2.is_mutable())
        self.failUnless(IURI.providedBy(u2))
        self.failUnless(IMutableFileURI.providedBy(u2))
        self.failIf(IDirnodeURI.providedBy(u2))

        u3 = u2.get_readonly()
        readkey = hashutil.ssk_readkey_hash(writekey)
        self.failUnlessEqual(u3.fingerprint, fingerprint)
        self.failUnlessEqual(u3.readkey, readkey)
        self.failUnless(u3.is_readonly())
        self.failUnless(u3.is_mutable())
        self.failUnless(IURI.providedBy(u3))
        self.failUnless(IMutableFileURI.providedBy(u3))
        self.failIf(IDirnodeURI.providedBy(u3))

        u4 = uri.ReadonlySSKFileURI(readkey, fingerprint)
        self.failUnlessEqual(u4.fingerprint, fingerprint)
        self.failUnlessEqual(u4.readkey, readkey)
        self.failUnless(u4.is_readonly())
        self.failUnless(u4.is_mutable())
        self.failUnless(IURI.providedBy(u4))
        self.failUnless(IMutableFileURI.providedBy(u4))
        self.failIf(IDirnodeURI.providedBy(u4))

        u4a = uri.from_string(u4.to_string())
        self.failUnlessEqual(u4a, u4)
        self.failUnless("ReadonlySSKFileURI" in str(u4a))
        self.failUnlessIdentical(u4a.get_readonly(), u4a)

        u5 = u4.get_verifier()
        self.failUnless(IVerifierURI.providedBy(u5))
        self.failUnlessEqual(u5.storage_index, u.storage_index)
        u6 = IVerifierURI(u5.to_string())
        self.failUnless(IVerifierURI.providedBy(u6))
        self.failUnlessEqual(u6.storage_index, u.storage_index)
        u7 = u.get_verifier()
        self.failUnless(IVerifierURI.providedBy(u7))
        self.failUnlessEqual(u7.storage_index, u.storage_index)


class NewDirnode(unittest.TestCase):
    def test_pack(self):
        writekey = "\x01" * 16
        fingerprint = "\x02" * 16

        n = uri.WriteableSSKFileURI(writekey, fingerprint)
        u1 = uri.NewDirectoryURI(n)
        self.failIf(u1.is_readonly())
        self.failUnless(u1.is_mutable())
        self.failUnless(IURI.providedBy(u1))
        self.failIf(IFileURI.providedBy(u1))
        self.failUnless(IDirnodeURI.providedBy(u1))
        self.failUnless("NewDirectoryURI" in str(u1))
        u1_filenode = u1.get_filenode_uri()
        self.failUnless(u1_filenode.is_mutable())
        self.failIf(u1_filenode.is_readonly())
        u1a = IDirnodeURI(u1.to_string())
        self.failUnlessEqual(u1a, u1)

        u2 = uri.from_string(u1.to_string())
        self.failUnlessEqual(u1.to_string(), u2.to_string())
        self.failIf(u2.is_readonly())
        self.failUnless(u2.is_mutable())
        self.failUnless(IURI.providedBy(u2))
        self.failIf(IFileURI.providedBy(u2))
        self.failUnless(IDirnodeURI.providedBy(u2))

        u3 = u2.get_readonly()
        self.failUnless(u3.is_readonly())
        self.failUnless(u3.is_mutable())
        self.failUnless(IURI.providedBy(u3))
        self.failIf(IFileURI.providedBy(u3))
        self.failUnless(IDirnodeURI.providedBy(u3))
        u3n = u3._filenode_uri
        self.failUnless(u3n.is_readonly())
        self.failUnless(u3n.is_mutable())
        u3_filenode = u3.get_filenode_uri()
        self.failUnless(u3_filenode.is_mutable())
        self.failUnless(u3_filenode.is_readonly())

        u3a = uri.from_string(u3.to_string())
        self.failUnlessIdentical(u3a, u3a.get_readonly())

        u4 = uri.ReadonlyNewDirectoryURI(u2._filenode_uri.get_readonly())
        self.failUnlessEqual(u4.to_string(), u3.to_string())
        self.failUnless(u4.is_readonly())
        self.failUnless(u4.is_mutable())
        self.failUnless(IURI.providedBy(u4))
        self.failIf(IFileURI.providedBy(u4))
        self.failUnless(IDirnodeURI.providedBy(u4))

        u4_verifier = u4.get_verifier()
        u4_verifier_filenode = u4_verifier.get_filenode_uri()
        self.failUnless(isinstance(u4_verifier_filenode, uri.SSKVerifierURI))

        verifiers = [u1.get_verifier(), u2.get_verifier(),
                     u3.get_verifier(), u4.get_verifier(),
                     IVerifierURI(u1.get_verifier().to_string()),
                     uri.NewDirectoryURIVerifier(n.get_verifier()),
                     uri.NewDirectoryURIVerifier(n.get_verifier().to_string()),
                     ]
        for v in verifiers:
            self.failUnless(IVerifierURI.providedBy(v))
            self.failUnlessEqual(v._filenode_uri,
                                 u1.get_verifier()._filenode_uri)

    def test_is_string_newdirnode_rw(self):
        writekey = "\x01" * 16
        fingerprint = "\x02" * 32

        n = uri.WriteableSSKFileURI(writekey, fingerprint)
        u1 = uri.NewDirectoryURI(n)

        self.failUnless(uri.is_string_newdirnode_rw(u1.to_string()), u1.to_string())

        self.failIf(uri.is_string_newdirnode_rw("bogus"))
        self.failIf(uri.is_string_newdirnode_rw("URI:DIR2:bogus"))

