
from twisted.trial import unittest

from cStringIO import StringIO
from twisted.python import usage, runtime
from twisted.internet import defer
import os.path, re
from allmydata.scripts import runner
from allmydata.util import fileutil, testutil

class CreateNode(unittest.TestCase):
    def workdir(self, name):
        basedir = os.path.join("test_runner", "CreateNode", name)
        fileutil.make_dirs(basedir)
        return basedir

    def test_client(self):
        basedir = self.workdir("test_client")
        c1 = os.path.join(basedir, "c1")
        argv = ["--quiet", "create-client", "--basedir", c1]
        out,err = StringIO(), StringIO()
        rc = runner.runner(argv, stdout=out, stderr=err)
        self.failUnlessEqual(err.getvalue(), "")
        self.failUnlessEqual(out.getvalue(), "")
        self.failUnlessEqual(rc, 0)
        self.failUnless(os.path.exists(c1))
        self.failUnless(os.path.exists(os.path.join(c1, "tahoe-client.tac")))

        # creating the client a second time should throw an exception
        out,err = StringIO(), StringIO()
        rc = runner.runner(argv, stdout=out, stderr=err)
        self.failIfEqual(rc, 0)
        self.failUnlessEqual(out.getvalue(), "")
        self.failUnless("is not empty." in err.getvalue())

        # Fail if there is a line that doesn't end with a PUNCTUATION MARK.
        self.failIf(re.search("[^\.!?]\n", err.getvalue()), err.getvalue())

        c2 = os.path.join(basedir, "c2")
        argv = ["--quiet", "create-client", c2]
        runner.runner(argv)
        self.failUnless(os.path.exists(c2))
        self.failUnless(os.path.exists(os.path.join(c2, "tahoe-client.tac")))

        self.failUnlessRaises(usage.UsageError,
                              runner.runner,
                              ["create-client", "basedir", "extraarg"],
                              run_by_human=False)

    def test_introducer(self):
        basedir = self.workdir("test_introducer")
        c1 = os.path.join(basedir, "c1")
        argv = ["--quiet", "create-introducer", "--basedir", c1]
        out,err = StringIO(), StringIO()
        rc = runner.runner(argv, stdout=out, stderr=err)
        self.failUnlessEqual(err.getvalue(), "")
        self.failUnlessEqual(out.getvalue(), "")
        self.failUnlessEqual(rc, 0)
        self.failUnless(os.path.exists(c1))
        self.failUnless(os.path.exists(os.path.join(c1,
                                                    "tahoe-introducer.tac")))

        # creating the introducer a second time should throw an exception
        out,err = StringIO(), StringIO()
        rc = runner.runner(argv, stdout=out, stderr=err)
        self.failIfEqual(rc, 0)
        self.failUnlessEqual(out.getvalue(), "")
        self.failUnless("is not empty" in err.getvalue())

        # Fail if there is a line that doesn't end with a PUNCTUATION MARK.
        self.failIf(re.search("[^\.!?]\n", err.getvalue()), err.getvalue())

        c2 = os.path.join(basedir, "c2")
        argv = ["--quiet", "create-introducer", c2]
        runner.runner(argv)
        self.failUnless(os.path.exists(c2))
        self.failUnless(os.path.exists(os.path.join(c2,
                                                    "tahoe-introducer.tac")))

        self.failUnlessRaises(usage.UsageError,
                              runner.runner,
                              ["create-introducer", "basedir", "extraarg"],
                              run_by_human=False)

        self.failUnlessRaises(usage.UsageError,
                              runner.runner,
                              ["create-introducer"],
                              run_by_human=False)

    def test_subcommands(self):
        self.failUnlessRaises(usage.UsageError,
                              runner.runner,
                              [],
                              run_by_human=False)

class RunNode(unittest.TestCase, testutil.PollMixin):
    def workdir(self, name):
        basedir = os.path.join("test_runner", "RunNode", name)
        fileutil.make_dirs(basedir)
        return basedir

    def test_client(self):
        if runtime.platformType == "win32":
            # twistd on windows doesn't daemonize. cygwin works normally.
            raise unittest.SkipTest("twistd does not fork under windows")
        basedir = self.workdir("test_client")
        c1 = os.path.join(basedir, "c1")
        argv = ["--quiet", "create-client", "--basedir", c1, "--webport", "0"]
        out,err = StringIO(), StringIO()
        rc = runner.runner(argv, stdout=out, stderr=err)
        self.failUnlessEqual(rc, 0)
        # by writing this file, we get ten seconds before the client will
        # exit. This insures that even if the test fails (and the 'stop'
        # command doesn't work), the client should still terminate.
        HOTLINE_FILE = os.path.join(c1, "suicide_prevention_hotline")
        open(HOTLINE_FILE, "w").write("")
        open(os.path.join(c1, "introducer.furl"), "w").write("pb://xrndsskn2zuuian5ltnxrte7lnuqdrkz@127.0.0.1:55617/introducer\n")
        # now it's safe to start the node

        TWISTD_PID_FILE = os.path.join(c1, "twistd.pid")

        d = defer.succeed(None)
        def _start(res):
            argv = ["--quiet", "start", c1]
            out,err = StringIO(), StringIO()
            rc = runner.runner(argv, stdout=out, stderr=err)
            open(HOTLINE_FILE, "w").write("")
            outs = out.getvalue() ; errs = err.getvalue()
            errstr = "rc=%d, OUT: '%s', ERR: '%s'" % (rc, outs, errs)
            self.failUnlessEqual(rc, 0, errstr)
            self.failUnlessEqual(outs, "", errstr)
            self.failUnlessEqual(errs, "", errstr)

            # the parent (twistd) has exited. However, twistd writes the pid
            # from the child, not the parent, so we can't expect twistd.pid
            # to exist quite yet.

            # the node is running, but it might not have made it past the
            # first reactor turn yet, and if we kill it too early, it won't
            # remove the twistd.pid file. So wait until it does something
            # that we know it won't do until after the first turn.

        d.addCallback(_start)

        PORTNUMFILE = os.path.join(c1, "client.port")
        def _node_has_started():
            return os.path.exists(PORTNUMFILE)
        d.addCallback(lambda res: self.poll(_node_has_started))

        def _started(res):
            open(HOTLINE_FILE, "w").write("")
            self.failUnless(os.path.exists(TWISTD_PID_FILE))
            # rm this so we can detect when the second incarnation is ready
            os.unlink(PORTNUMFILE)
            argv = ["--quiet", "restart", c1]
            out,err = StringIO(), StringIO()
            rc = runner.runner(argv, stdout=out, stderr=err)
            open(HOTLINE_FILE, "w").write("")
            outs = out.getvalue() ; errs = err.getvalue()
            errstr = "rc=%d, OUT: '%s', ERR: '%s'" % (rc, outs, errs)
            self.failUnlessEqual(rc, 0, errstr)
            self.failUnlessEqual(outs, "", errstr)
            self.failUnlessEqual(errs, "", errstr)
        d.addCallback(_started)

        # again, the second incarnation of the node might not be ready yet,
        # so poll until it is
        d.addCallback(lambda res: self.poll(_node_has_started))

        # now we can kill it. TODO: On a slow machine, the node might kill
        # itself before we get a chance too, especially if spawning the
        # 'tahoe stop' command takes a while.
        def _stop(res):
            open(HOTLINE_FILE, "w").write("")
            self.failUnless(os.path.exists(TWISTD_PID_FILE))
            argv = ["--quiet", "stop", c1]
            out,err = StringIO(), StringIO()
            rc = runner.runner(argv, stdout=out, stderr=err)
            open(HOTLINE_FILE, "w").write("")
            # the parent has exited by now
            outs = out.getvalue() ; errs = err.getvalue()
            errstr = "rc=%d, OUT: '%s', ERR: '%s'" % (rc, outs, errs)
            self.failUnlessEqual(rc, 0, errstr)
            self.failUnlessEqual(outs, "", errstr)
            self.failUnlessEqual(errs, "", errstr)
            # the parent was supposed to poll and wait until it sees
            # twistd.pid go away before it exits, so twistd.pid should be
            # gone by now.
            self.failIf(os.path.exists(TWISTD_PID_FILE))
        d.addCallback(_stop)
        def _remove_hotline(res):
            os.unlink(HOTLINE_FILE)
            return res
        d.addBoth(_remove_hotline)
        return d

    def test_baddir(self):
        basedir = self.workdir("test_baddir")
        fileutil.make_dirs(basedir)
        argv = ["--quiet", "start", "--basedir", basedir]
        out,err = StringIO(), StringIO()
        rc = runner.runner(argv, stdout=out, stderr=err)
        self.failUnlessEqual(rc, 1)
        self.failUnless("does not look like a node directory" in err.getvalue())

        argv = ["--quiet", "stop", "--basedir", basedir]
        out,err = StringIO(), StringIO()
        rc = runner.runner(argv, stdout=out, stderr=err)
        self.failUnlessEqual(rc, 2)
        self.failUnless("does not look like a running node directory"
                        in err.getvalue())

        not_a_dir = os.path.join(basedir, "bogus")
        argv = ["--quiet", "start", "--basedir", not_a_dir]
        out,err = StringIO(), StringIO()
        rc = runner.runner(argv, stdout=out, stderr=err)
        self.failUnlessEqual(rc, 1)
        self.failUnless("does not look like a directory at all"
                        in err.getvalue(), err.getvalue())


