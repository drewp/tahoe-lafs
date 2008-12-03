# coding=utf-8

import os.path
from twisted.trial import unittest
from cStringIO import StringIO
import urllib

from allmydata.util import fileutil, hashutil
from allmydata import uri

# Test that the scripts can be imported -- although the actual tests of their functionality are
# done by invoking them in a subprocess.
from allmydata.scripts import tahoe_ls, tahoe_get, tahoe_put, tahoe_rm, tahoe_cp
_hush_pyflakes = [tahoe_ls, tahoe_get, tahoe_put, tahoe_rm, tahoe_cp]

from allmydata.scripts.common import DEFAULT_ALIAS, get_aliases

from allmydata.scripts import cli, debug, runner
from allmydata.test.common import SystemTestMixin
from twisted.internet import threads # CLI tests use deferToThread

class CLI(unittest.TestCase):
    # this test case only looks at argument-processing and simple stuff.
    def test_options(self):
        fileutil.rm_dir("cli/test_options")
        fileutil.make_dirs("cli/test_options")
        fileutil.make_dirs("cli/test_options/private")
        open("cli/test_options/node.url","w").write("http://localhost:8080/\n")
        filenode_uri = uri.WriteableSSKFileURI(writekey="\x00"*16,
                                               fingerprint="\x00"*32)
        private_uri = uri.NewDirectoryURI(filenode_uri).to_string()
        open("cli/test_options/private/root_dir.cap", "w").write(private_uri + "\n")
        o = cli.ListOptions()
        o.parseOptions(["--node-directory", "cli/test_options"])
        self.failUnlessEqual(o['node-url'], "http://localhost:8080/")
        self.failUnlessEqual(o.aliases[DEFAULT_ALIAS], private_uri)
        self.failUnlessEqual(o.where, "")

        o = cli.ListOptions()
        o.parseOptions(["--node-directory", "cli/test_options",
                        "--node-url", "http://example.org:8111/"])
        self.failUnlessEqual(o['node-url'], "http://example.org:8111/")
        self.failUnlessEqual(o.aliases[DEFAULT_ALIAS], private_uri)
        self.failUnlessEqual(o.where, "")

        o = cli.ListOptions()
        o.parseOptions(["--node-directory", "cli/test_options",
                        "--dir-cap", "root"])
        self.failUnlessEqual(o['node-url'], "http://localhost:8080/")
        self.failUnlessEqual(o.aliases[DEFAULT_ALIAS], "root")
        self.failUnlessEqual(o.where, "")

        o = cli.ListOptions()
        other_filenode_uri = uri.WriteableSSKFileURI(writekey="\x11"*16,
                                                     fingerprint="\x11"*32)
        other_uri = uri.NewDirectoryURI(other_filenode_uri).to_string()
        o.parseOptions(["--node-directory", "cli/test_options",
                        "--dir-cap", other_uri])
        self.failUnlessEqual(o['node-url'], "http://localhost:8080/")
        self.failUnlessEqual(o.aliases[DEFAULT_ALIAS], other_uri)
        self.failUnlessEqual(o.where, "")

        o = cli.ListOptions()
        o.parseOptions(["--node-directory", "cli/test_options",
                        "--dir-cap", other_uri, "subdir"])
        self.failUnlessEqual(o['node-url'], "http://localhost:8080/")
        self.failUnlessEqual(o.aliases[DEFAULT_ALIAS], other_uri)
        self.failUnlessEqual(o.where, "subdir")

    def _dump_cap(self, *args):
        config = debug.DumpCapOptions()
        config.stdout,config.stderr = StringIO(), StringIO()
        config.parseOptions(args)
        debug.dump_cap(config)
        self.failIf(config.stderr.getvalue())
        output = config.stdout.getvalue()
        return output

    def test_dump_cap_chk(self):
        key = "\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f"
        storage_index = hashutil.storage_index_hash(key)
        uri_extension_hash = hashutil.uri_extension_hash("stuff")
        needed_shares = 25
        total_shares = 100
        size = 1234
        u = uri.CHKFileURI(key=key,
                           uri_extension_hash=uri_extension_hash,
                           needed_shares=needed_shares,
                           total_shares=total_shares,
                           size=size)
        output = self._dump_cap(u.to_string())
        self.failUnless("CHK File:" in output, output)
        self.failUnless("key: aaaqeayeaudaocajbifqydiob4" in output, output)
        self.failUnless("UEB hash: nf3nimquen7aeqm36ekgxomalstenpkvsdmf6fplj7swdatbv5oa" in output, output)
        self.failUnless("size: 1234" in output, output)
        self.failUnless("k/N: 25/100" in output, output)
        self.failUnless("storage index: hdis5iaveku6lnlaiccydyid7q" in output, output)

        output = self._dump_cap("--client-secret", "5s33nk3qpvnj2fw3z4mnm2y6fa",
                                u.to_string())
        self.failUnless("client renewal secret: znxmki5zdibb5qlt46xbdvk2t55j7hibejq3i5ijyurkr6m6jkhq" in output, output)

        output = self._dump_cap(u.get_verifier().to_string())
        self.failIf("key: " in output, output)
        self.failUnless("UEB hash: nf3nimquen7aeqm36ekgxomalstenpkvsdmf6fplj7swdatbv5oa" in output, output)
        self.failUnless("size: 1234" in output, output)
        self.failUnless("k/N: 25/100" in output, output)
        self.failUnless("storage index: hdis5iaveku6lnlaiccydyid7q" in output, output)

        prefixed_u = "http://127.0.0.1/uri/%s" % urllib.quote(u.to_string())
        output = self._dump_cap(prefixed_u)
        self.failUnless("CHK File:" in output, output)
        self.failUnless("key: aaaqeayeaudaocajbifqydiob4" in output, output)
        self.failUnless("UEB hash: nf3nimquen7aeqm36ekgxomalstenpkvsdmf6fplj7swdatbv5oa" in output, output)
        self.failUnless("size: 1234" in output, output)
        self.failUnless("k/N: 25/100" in output, output)
        self.failUnless("storage index: hdis5iaveku6lnlaiccydyid7q" in output, output)

    def test_dump_cap_lit(self):
        u = uri.LiteralFileURI("this is some data")
        output = self._dump_cap(u.to_string())
        self.failUnless("Literal File URI:" in output, output)
        self.failUnless("data: this is some data" in output, output)

    def test_dump_cap_ssk(self):
        writekey = "\x01" * 16
        fingerprint = "\xfe" * 32
        u = uri.WriteableSSKFileURI(writekey, fingerprint)

        output = self._dump_cap(u.to_string())
        self.failUnless("SSK Writeable URI:" in output, output)
        self.failUnless("writekey: aeaqcaibaeaqcaibaeaqcaibae" in output, output)
        self.failUnless("readkey: nvgh5vj2ekzzkim5fgtb4gey5y" in output, output)
        self.failUnless("storage index: nt4fwemuw7flestsezvo2eveke" in output, output)
        self.failUnless("fingerprint: 737p57x6737p57x6737p57x6737p57x6737p57x6737p57x6737a" in output, output)

        output = self._dump_cap("--client-secret", "5s33nk3qpvnj2fw3z4mnm2y6fa",
                                u.to_string())
        self.failUnless("file renewal secret: arpszxzc2t6kb4okkg7sp765xgkni5z7caavj7lta73vmtymjlxq" in output, output)

        fileutil.make_dirs("cli/test_dump_cap/private")
        f = open("cli/test_dump_cap/private/secret", "w")
        f.write("5s33nk3qpvnj2fw3z4mnm2y6fa\n")
        f.close()
        output = self._dump_cap("--client-dir", "cli/test_dump_cap",
                                u.to_string())
        self.failUnless("file renewal secret: arpszxzc2t6kb4okkg7sp765xgkni5z7caavj7lta73vmtymjlxq" in output, output)

        output = self._dump_cap("--client-dir", "cli/test_dump_cap_BOGUS",
                                u.to_string())
        self.failIf("file renewal secret:" in output, output)

        output = self._dump_cap("--nodeid", "tqc35esocrvejvg4mablt6aowg6tl43j",
                                u.to_string())
        self.failUnless("write_enabler: mgcavriox2wlb5eer26unwy5cw56elh3sjweffckkmivvsxtaknq" in output, output)
        self.failIf("file renewal secret:" in output, output)

        output = self._dump_cap("--nodeid", "tqc35esocrvejvg4mablt6aowg6tl43j",
                                "--client-secret", "5s33nk3qpvnj2fw3z4mnm2y6fa",
                                u.to_string())
        self.failUnless("write_enabler: mgcavriox2wlb5eer26unwy5cw56elh3sjweffckkmivvsxtaknq" in output, output)
        self.failUnless("file renewal secret: arpszxzc2t6kb4okkg7sp765xgkni5z7caavj7lta73vmtymjlxq" in output, output)
        self.failUnless("lease renewal secret: 7pjtaumrb7znzkkbvekkmuwpqfjyfyamznfz4bwwvmh4nw33lorq" in output, output)

        u = u.get_readonly()
        output = self._dump_cap(u.to_string())
        self.failUnless("SSK Read-only URI:" in output, output)
        self.failUnless("readkey: nvgh5vj2ekzzkim5fgtb4gey5y" in output, output)
        self.failUnless("storage index: nt4fwemuw7flestsezvo2eveke" in output, output)
        self.failUnless("fingerprint: 737p57x6737p57x6737p57x6737p57x6737p57x6737p57x6737a" in output, output)

        u = u.get_verifier()
        output = self._dump_cap(u.to_string())
        self.failUnless("SSK Verifier URI:" in output, output)
        self.failUnless("storage index: nt4fwemuw7flestsezvo2eveke" in output, output)
        self.failUnless("fingerprint: 737p57x6737p57x6737p57x6737p57x6737p57x6737p57x6737a" in output, output)

    def test_dump_cap_directory(self):
        writekey = "\x01" * 16
        fingerprint = "\xfe" * 32
        u1 = uri.WriteableSSKFileURI(writekey, fingerprint)
        u = uri.NewDirectoryURI(u1)

        output = self._dump_cap(u.to_string())
        self.failUnless("Directory Writeable URI:" in output, output)
        self.failUnless("writekey: aeaqcaibaeaqcaibaeaqcaibae" in output,
                        output)
        self.failUnless("readkey: nvgh5vj2ekzzkim5fgtb4gey5y" in output, output)
        self.failUnless("storage index: nt4fwemuw7flestsezvo2eveke" in output,
                        output)
        self.failUnless("fingerprint: 737p57x6737p57x6737p57x6737p57x6737p57x6737p57x6737a" in output, output)

        output = self._dump_cap("--client-secret", "5s33nk3qpvnj2fw3z4mnm2y6fa",
                                u.to_string())
        self.failUnless("file renewal secret: arpszxzc2t6kb4okkg7sp765xgkni5z7caavj7lta73vmtymjlxq" in output, output)

        output = self._dump_cap("--nodeid", "tqc35esocrvejvg4mablt6aowg6tl43j",
                                u.to_string())
        self.failUnless("write_enabler: mgcavriox2wlb5eer26unwy5cw56elh3sjweffckkmivvsxtaknq" in output, output)
        self.failIf("file renewal secret:" in output, output)

        output = self._dump_cap("--nodeid", "tqc35esocrvejvg4mablt6aowg6tl43j",
                                "--client-secret", "5s33nk3qpvnj2fw3z4mnm2y6fa",
                                u.to_string())
        self.failUnless("write_enabler: mgcavriox2wlb5eer26unwy5cw56elh3sjweffckkmivvsxtaknq" in output, output)
        self.failUnless("file renewal secret: arpszxzc2t6kb4okkg7sp765xgkni5z7caavj7lta73vmtymjlxq" in output, output)
        self.failUnless("lease renewal secret: 7pjtaumrb7znzkkbvekkmuwpqfjyfyamznfz4bwwvmh4nw33lorq" in output, output)

        u = u.get_readonly()
        output = self._dump_cap(u.to_string())
        self.failUnless("Directory Read-only URI:" in output, output)
        self.failUnless("readkey: nvgh5vj2ekzzkim5fgtb4gey5y" in output, output)
        self.failUnless("storage index: nt4fwemuw7flestsezvo2eveke" in output, output)
        self.failUnless("fingerprint: 737p57x6737p57x6737p57x6737p57x6737p57x6737p57x6737a" in output, output)

        u = u.get_verifier()
        output = self._dump_cap(u.to_string())
        self.failUnless("Directory Verifier URI:" in output, output)
        self.failUnless("storage index: nt4fwemuw7flestsezvo2eveke" in output, output)
        self.failUnless("fingerprint: 737p57x6737p57x6737p57x6737p57x6737p57x6737p57x6737a" in output, output)

    def _catalog_shares(self, *basedirs):
        o = debug.CatalogSharesOptions()
        o.stdout,o.stderr = StringIO(), StringIO()
        args = list(basedirs)
        o.parseOptions(args)
        debug.catalog_shares(o)
        out = o.stdout.getvalue()
        err = o.stderr.getvalue()
        return out, err

    def test_catalog_shares_error(self):
        nodedir1 = "cli/test_catalog_shares/node1"
        sharedir = os.path.join(nodedir1, "storage", "shares", "mq", "mqfblse6m5a6dh45isu2cg7oji")
        fileutil.make_dirs(sharedir)
        f = open(os.path.join(sharedir, "8"), "wb")
        open("cli/test_catalog_shares/node1/storage/shares/mq/not-a-dir", "wb").close()
        # write a bogus share that looks a little bit like CHK
        f.write("\x00\x00\x00\x01" + "\xff" * 200) # this triggers an assert
        f.close()

        nodedir2 = "cli/test_catalog_shares/node2"
        fileutil.make_dirs(nodedir2)
        open("cli/test_catalog_shares/node1/storage/shares/not-a-dir", "wb").close()

        # now make sure that the 'catalog-shares' commands survives the error
        out, err = self._catalog_shares(nodedir1, nodedir2)
        self.failUnlessEqual(out, "", out)
        self.failUnless("Error processing " in err,
                        "didn't see 'error processing' in '%s'" % err)
        #self.failUnless(nodedir1 in err,
        #                "didn't see '%s' in '%s'" % (nodedir1, err))
        # windows mangles the path, and os.path.join isn't enough to make
        # up for it, so just look for individual strings
        self.failUnless("node1" in err,
                        "didn't see 'node1' in '%s'" % err)
        self.failUnless("mqfblse6m5a6dh45isu2cg7oji" in err,
                        "didn't see 'mqfblse6m5a6dh45isu2cg7oji' in '%s'" % err)


class CLITestMixin:
    def do_cli(self, verb, *args, **kwargs):
        nodeargs = [
            "--node-directory", self.getdir("client0"),
            ]
        argv = [verb] + nodeargs + list(args)
        stdin = kwargs.get("stdin", "")
        stdout, stderr = StringIO(), StringIO()
        d = threads.deferToThread(runner.runner, argv, run_by_human=False,
                                  stdin=StringIO(stdin),
                                  stdout=stdout, stderr=stderr)
        def _done(rc):
            return rc, stdout.getvalue(), stderr.getvalue()
        d.addCallback(_done)
        return d

class CreateAlias(SystemTestMixin, CLITestMixin, unittest.TestCase):

    def _test_webopen(self, args, expected_url):
        woo = cli.WebopenOptions()
        all_args = ["--node-directory", self.getdir("client0")] + list(args)
        woo.parseOptions(all_args)
        urls = []
        rc = cli.webopen(woo, urls.append)
        self.failUnlessEqual(rc, 0)
        self.failUnlessEqual(len(urls), 1)
        self.failUnlessEqual(urls[0], expected_url)

    def test_create(self):
        self.basedir = os.path.dirname(self.mktemp())
        d = self.set_up_nodes()
        d.addCallback(lambda res: self.do_cli("create-alias", "tahoe"))
        def _done((rc,stdout,stderr)):
            self.failUnless("Alias 'tahoe' created" in stdout)
            self.failIf(stderr)
            aliases = get_aliases(self.getdir("client0"))
            self.failUnless("tahoe" in aliases)
            self.failUnless(aliases["tahoe"].startswith("URI:DIR2:"))
        d.addCallback(_done)
        d.addCallback(lambda res: self.do_cli("create-alias", "two"))

        def _stash_urls(res):
            aliases = get_aliases(self.getdir("client0"))
            node_url_file = os.path.join(self.getdir("client0"), "node.url")
            nodeurl = open(node_url_file, "r").read().strip()
            uribase = nodeurl + "uri/"
            self.tahoe_url = uribase + urllib.quote(aliases["tahoe"])
            self.tahoe_subdir_url = self.tahoe_url + "/subdir"
            self.two_url = uribase + urllib.quote(aliases["two"])
            self.two_uri = aliases["two"]
        d.addCallback(_stash_urls)

        d.addCallback(lambda res: self.do_cli("create-alias", "two")) # dup
        def _check_create_duplicate((rc,stdout,stderr)):
            self.failIfEqual(rc, 0)
            self.failUnless("Alias 'two' already exists!" in stderr)
            aliases = get_aliases(self.getdir("client0"))
            self.failUnlessEqual(aliases["two"], self.two_uri)
        d.addCallback(_check_create_duplicate)

        d.addCallback(lambda res: self.do_cli("add-alias", "added", self.two_uri))
        def _check_add((rc,stdout,stderr)):
            self.failUnlessEqual(rc, 0)
            self.failUnless("Alias 'added' added" in stdout)
        d.addCallback(_check_add)

        # check add-alias with a duplicate
        d.addCallback(lambda res: self.do_cli("add-alias", "two", self.two_uri))
        def _check_add_duplicate((rc,stdout,stderr)):
            self.failIfEqual(rc, 0)
            self.failUnless("Alias 'two' already exists!" in stderr)
            aliases = get_aliases(self.getdir("client0"))
            self.failUnlessEqual(aliases["two"], self.two_uri)
        d.addCallback(_check_add_duplicate)

        def _test_urls(junk):
            self._test_webopen([], self.tahoe_url)
            self._test_webopen(["/"], self.tahoe_url)
            self._test_webopen(["tahoe:"], self.tahoe_url)
            self._test_webopen(["tahoe:/"], self.tahoe_url)
            self._test_webopen(["tahoe:subdir"], self.tahoe_subdir_url)
            self._test_webopen(["tahoe:subdir/"], self.tahoe_subdir_url + '/')
            self._test_webopen(["tahoe:subdir/file"], self.tahoe_subdir_url + '/file')
            # if "file" is indeed a file, then the url produced by webopen in
            # this case is disallowed by the webui. but by design, webopen
            # passes through the mistake from the user to the resultant
            # webopened url
            self._test_webopen(["tahoe:subdir/file/"], self.tahoe_subdir_url + '/file/')
            self._test_webopen(["two:"], self.two_url)
        d.addCallback(_test_urls)

        return d

class Put(SystemTestMixin, CLITestMixin, unittest.TestCase):

    def test_unlinked_immutable_stdin(self):
        # tahoe get `echo DATA | tahoe put`
        # tahoe get `echo DATA | tahoe put -`

        self.basedir = self.mktemp()
        DATA = "data" * 100
        d = self.set_up_nodes()
        d.addCallback(lambda res: self.do_cli("put", stdin=DATA))
        def _uploaded(res):
            (rc, stdout, stderr) = res
            self.failUnless("waiting for file data on stdin.." in stderr)
            self.failUnless("200 OK" in stderr, stderr)
            self.readcap = stdout
            self.failUnless(self.readcap.startswith("URI:CHK:"))
        d.addCallback(_uploaded)
        d.addCallback(lambda res: self.do_cli("get", self.readcap))
        def _downloaded(res):
            (rc, stdout, stderr) = res
            self.failUnlessEqual(stderr, "")
            self.failUnlessEqual(stdout, DATA)
        d.addCallback(_downloaded)
        d.addCallback(lambda res: self.do_cli("put", "-", stdin=DATA))
        d.addCallback(lambda (rc,stdout,stderr):
                      self.failUnlessEqual(stdout, self.readcap))
        return d

    def test_unlinked_immutable_from_file(self):
        # tahoe put file.txt
        # tahoe put ./file.txt
        # tahoe put /tmp/file.txt
        # tahoe put ~/file.txt
        self.basedir = os.path.dirname(self.mktemp())
        # this will be "allmydata.test.test_cli/Put/test_put_from_file/RANDOM"
        # and the RANDOM directory will exist. Raw mktemp returns a filename.

        rel_fn = os.path.join(self.basedir, "DATAFILE")
        abs_fn = os.path.abspath(rel_fn)
        # we make the file small enough to fit in a LIT file, for speed
        f = open(rel_fn, "w")
        f.write("short file")
        f.close()
        d = self.set_up_nodes()
        d.addCallback(lambda res: self.do_cli("put", rel_fn))
        def _uploaded((rc,stdout,stderr)):
            readcap = stdout
            self.failUnless(readcap.startswith("URI:LIT:"))
            self.readcap = readcap
        d.addCallback(_uploaded)
        d.addCallback(lambda res: self.do_cli("put", "./" + rel_fn))
        d.addCallback(lambda (rc,stdout,stderr):
                      self.failUnlessEqual(stdout, self.readcap))
        d.addCallback(lambda res: self.do_cli("put", abs_fn))
        d.addCallback(lambda (rc,stdout,stderr):
                      self.failUnlessEqual(stdout, self.readcap))
        # we just have to assume that ~ is handled properly
        return d

    def test_immutable_from_file(self):
        # tahoe put file.txt uploaded.txt
        # tahoe - uploaded.txt
        # tahoe put file.txt subdir/uploaded.txt
        # tahoe put file.txt tahoe:uploaded.txt
        # tahoe put file.txt tahoe:subdir/uploaded.txt
        # tahoe put file.txt DIRCAP:./uploaded.txt
        # tahoe put file.txt DIRCAP:./subdir/uploaded.txt
        self.basedir = os.path.dirname(self.mktemp())

        rel_fn = os.path.join(self.basedir, "DATAFILE")
        abs_fn = os.path.abspath(rel_fn)
        # we make the file small enough to fit in a LIT file, for speed
        DATA = "short file"
        DATA2 = "short file two"
        f = open(rel_fn, "w")
        f.write(DATA)
        f.close()

        d = self.set_up_nodes()
        d.addCallback(lambda res: self.do_cli("create-alias", "tahoe"))

        d.addCallback(lambda res:
                      self.do_cli("put", rel_fn, "uploaded.txt"))
        def _uploaded((rc,stdout,stderr)):
            readcap = stdout.strip()
            self.failUnless(readcap.startswith("URI:LIT:"))
            self.failUnless("201 Created" in stderr, stderr)
            self.readcap = readcap
        d.addCallback(_uploaded)
        d.addCallback(lambda res:
                      self.do_cli("get", "tahoe:uploaded.txt"))
        d.addCallback(lambda (rc,stdout,stderr):
                      self.failUnlessEqual(stdout, DATA))

        d.addCallback(lambda res:
                      self.do_cli("put", "-", "uploaded.txt", stdin=DATA2))
        def _replaced((rc,stdout,stderr)):
            readcap = stdout.strip()
            self.failUnless(readcap.startswith("URI:LIT:"))
            self.failUnless("200 OK" in stderr, stderr)
        d.addCallback(_replaced)

        d.addCallback(lambda res:
                      self.do_cli("put", rel_fn, "subdir/uploaded2.txt"))
        d.addCallback(lambda res: self.do_cli("get", "subdir/uploaded2.txt"))
        d.addCallback(lambda (rc,stdout,stderr):
                      self.failUnlessEqual(stdout, DATA))

        d.addCallback(lambda res:
                      self.do_cli("put", rel_fn, "tahoe:uploaded3.txt"))
        d.addCallback(lambda res: self.do_cli("get", "tahoe:uploaded3.txt"))
        d.addCallback(lambda (rc,stdout,stderr):
                      self.failUnlessEqual(stdout, DATA))

        d.addCallback(lambda res:
                      self.do_cli("put", rel_fn, "tahoe:subdir/uploaded4.txt"))
        d.addCallback(lambda res:
                      self.do_cli("get", "tahoe:subdir/uploaded4.txt"))
        d.addCallback(lambda (rc,stdout,stderr):
                      self.failUnlessEqual(stdout, DATA))

        def _get_dircap(res):
            self.dircap = get_aliases(self.getdir("client0"))["tahoe"]
        d.addCallback(_get_dircap)

        d.addCallback(lambda res:
                      self.do_cli("put", rel_fn,
                                  self.dircap+":./uploaded5.txt"))
        d.addCallback(lambda res:
                      self.do_cli("get", "tahoe:uploaded5.txt"))
        d.addCallback(lambda (rc,stdout,stderr):
                      self.failUnlessEqual(stdout, DATA))

        d.addCallback(lambda res:
                      self.do_cli("put", rel_fn,
                                  self.dircap+":./subdir/uploaded6.txt"))
        d.addCallback(lambda res:
                      self.do_cli("get", "tahoe:subdir/uploaded6.txt"))
        d.addCallback(lambda (rc,stdout,stderr):
                      self.failUnlessEqual(stdout, DATA))

        return d

    def test_mutable_unlinked(self):
        # FILECAP = `echo DATA | tahoe put --mutable`
        # tahoe get FILECAP, compare against DATA
        # echo DATA2 | tahoe put - FILECAP
        # tahoe get FILECAP, compare against DATA2
        # tahoe put file.txt FILECAP
        self.basedir = os.path.dirname(self.mktemp())
        DATA = "data" * 100
        DATA2 = "two" * 100
        rel_fn = os.path.join(self.basedir, "DATAFILE")
        abs_fn = os.path.abspath(rel_fn)
        DATA3 = "three" * 100
        f = open(rel_fn, "w")
        f.write(DATA3)
        f.close()

        d = self.set_up_nodes()

        d.addCallback(lambda res: self.do_cli("put", "--mutable", stdin=DATA))
        def _created(res):
            (rc, stdout, stderr) = res
            self.failUnless("waiting for file data on stdin.." in stderr)
            self.failUnless("200 OK" in stderr)
            self.filecap = stdout
            self.failUnless(self.filecap.startswith("URI:SSK:"))
        d.addCallback(_created)
        d.addCallback(lambda res: self.do_cli("get", self.filecap))
        d.addCallback(lambda (rc,out,err): self.failUnlessEqual(out, DATA))

        d.addCallback(lambda res: self.do_cli("put", "-", self.filecap, stdin=DATA2))
        def _replaced(res):
            (rc, stdout, stderr) = res
            self.failUnless("waiting for file data on stdin.." in stderr)
            self.failUnless("200 OK" in stderr)
            self.failUnlessEqual(self.filecap, stdout)
        d.addCallback(_replaced)
        d.addCallback(lambda res: self.do_cli("get", self.filecap))
        d.addCallback(lambda (rc,out,err): self.failUnlessEqual(out, DATA2))

        d.addCallback(lambda res: self.do_cli("put", rel_fn, self.filecap))
        def _replaced2(res):
            (rc, stdout, stderr) = res
            self.failUnless("200 OK" in stderr)
            self.failUnlessEqual(self.filecap, stdout)
        d.addCallback(_replaced2)
        d.addCallback(lambda res: self.do_cli("get", self.filecap))
        d.addCallback(lambda (rc,out,err): self.failUnlessEqual(out, DATA3))

        return d

    def test_mutable(self):
        # echo DATA1 | tahoe put --mutable - uploaded.txt
        # echo DATA2 | tahoe put - uploaded.txt # should modify-in-place
        # tahoe get uploaded.txt, compare against DATA2

        self.basedir = os.path.dirname(self.mktemp())
        DATA1 = "data" * 100
        fn1 = os.path.join(self.basedir, "DATA1")
        f = open(fn1, "w")
        f.write(DATA1)
        f.close()
        DATA2 = "two" * 100
        fn2 = os.path.join(self.basedir, "DATA2")
        f = open(fn2, "w")
        f.write(DATA2)
        f.close()

        d = self.set_up_nodes()
        d.addCallback(lambda res: self.do_cli("create-alias", "tahoe"))
        d.addCallback(lambda res:
                      self.do_cli("put", "--mutable", fn1, "tahoe:uploaded.txt"))
        d.addCallback(lambda res:
                      self.do_cli("put", fn2, "tahoe:uploaded.txt"))
        d.addCallback(lambda res:
                      self.do_cli("get", "tahoe:uploaded.txt"))
        d.addCallback(lambda (rc,out,err): self.failUnlessEqual(out, DATA2))
        return d

class Cp(SystemTestMixin, CLITestMixin, unittest.TestCase):
    def test_unicode_filename(self):
        self.basedir = os.path.dirname(self.mktemp())

        fn1 = os.path.join(self.basedir, "Ärtonwall")
        DATA1 = "unicode file content"
        open(fn1, "wb").write(DATA1)

        fn2 = os.path.join(self.basedir, "Metallica")
        DATA2 = "non-unicode file content"
        open(fn2, "wb").write(DATA2)

        # Bug #534
        # Assure that uploading a file whose name contains unicode character doesn't
        # prevent further uploads in the same directory
        d = self.set_up_nodes()
        d.addCallback(lambda res: self.do_cli("create-alias", "tahoe"))
        d.addCallback(lambda res: self.do_cli("cp", fn1, "tahoe:"))
        d.addCallback(lambda res: self.do_cli("cp", fn2, "tahoe:"))

        d.addCallback(lambda res: self.do_cli("get", "tahoe:Ärtonwall"))
        d.addCallback(lambda (rc,out,err): self.failUnlessEqual(out, DATA1))

        d.addCallback(lambda res: self.do_cli("get", "tahoe:Metallica"))
        d.addCallback(lambda (rc,out,err): self.failUnlessEqual(out, DATA2))

        return d
