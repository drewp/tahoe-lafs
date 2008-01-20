#! /usr/bin/env python
'''
Unit tests for tahoe-fuse.

Note: The API design of the python-fuse library makes unit testing much
of tahoe-fuse.py tricky business.
'''

import sys, os, shutil, unittest, subprocess, tempfile, re, time

import tahoe_fuse


### Main flow control:
def main(args = sys.argv[1:]):
    target = 'all'
    if args:
        if len(args) != 1:
            raise SystemExit(Usage)
        target = args[0]

    if target not in ('all', 'unit', 'system'):
        raise SystemExit(Usage)
        
    if target in ('all', 'unit'):
        run_unit_tests()

    if target in ('all', 'system'):
        run_system_test()


def run_unit_tests():
    print 'Running Unit Tests.'
    try:
        unittest.main()
    except SystemExit, se:
        pass
    print 'Unit Tests complete.\n'
    

def run_system_test():
    SystemTest().run()


### System Testing:
class SystemTest (object):
    def __init__(self):
        self.cliexec = None
        self.introbase = None
        self.clientbase = None

    ## Top-level flow control:
    # These "*_layer" methods call eachother in a linear fashion, using
    # exception unwinding to do cleanup properly.  Each "layer" invokes
    # a deeper layer, and each layer does its own cleanup upon exit.
    
    def run(self):
        print 'Running System Test.'
        try:
            self.init_cli_layer()
        except self.SetupFailure, sfail:
            print
            print sfail

        print 'System Test complete.'

    def init_cli_layer(self):
        '''This layer finds the appropriate tahoe executable.'''
        runtestpath = os.path.abspath(sys.argv[0])
        path = runtestpath
        for expectedname in ('runtests.py', 'fuse', 'contrib'):
            path, name = os.path.split(path)

            if name != expectedname:
                reason = 'Unexpected test script path: %r\n'
                reason += 'The system test script must be run from the source directory.'
                raise self.SetupFailure(reason, runtestpath)

        self.cliexec = os.path.join(path, 'bin', 'tahoe')
        version = self.run_tahoe('--version')
        print 'Using %r with version:\n%s' % (self.cliexec, version.rstrip())

        self.create_introducer_layer()
        
    def create_introducer_layer(self):
        print 'Creating introducer.'
        self.introbase = tempfile.mkdtemp(prefix='tahoe_fuse_test_',
                                          suffix='_introducer')
        try:
            output = self.run_tahoe('create-introducer', '--basedir', self.introbase)

            pat = r'^introducer created in (.*?)\n\s*$'
            self.check_tahoe_output(output, pat, self.introbase)

            self.launch_introducer_layer()
            
        finally:
            print 'Removing introducer directory.'
            self.cleanup_dir(self.introbase)
    
    def launch_introducer_layer(self):
        print 'Launching introducer.'
        # NOTE: We assume if tahoe exist with non-zero status, no separate
        # tahoe child process is still running.
        output = self.run_tahoe('start', '--basedir', self.introbase)
        try:
            pat = r'^STARTING (.*?)\nintroducer node probably started\s*$'
            self.check_tahoe_output(output, pat, self.introbase)

            self.create_client_layer()
            
        finally:
            print 'Stopping introducer node.'
            try:
                output = self.run_tahoe('stop', '--basedir', self.introbase)
            except Exception, e:
                print 'Failed to stop introducer node.  Output:'
                print output
                print 'Ignoring cleanup exception: %r' % (e,)
        
    def create_client_layer(self):
        print 'Creating client.'
        self.clientbase = tempfile.mkdtemp(prefix='tahoe_fuse_test_',
                                           suffix='_client')
        try:
            output = self.run_tahoe('create-client', '--basedir', self.clientbase)
            pat = r'^client created in (.*?)\n'
            pat += r' please copy introducer.furl into the directory\s*$'
            self.check_tahoe_output(output, pat, self.clientbase)

            self.configure_client_layer()
            
        finally:
            print 'Removing client directory.'
            self.cleanup_dir(self.clientbase)
    
    def configure_client_layer(self):
        print 'Configuring client.'

        introfurl = os.path.join(self.introbase, 'introducer.furl')

        # FIXME: Is there a better way to handle this race condition?
        timeout = 10.0 # Timeout seconds.
        pollinterval = 0.2
        totalattempts = int(timeout / pollinterval)

        for attempts in range(totalattempts):
            if os.path.isfile(introfurl):
                tmpl = '(It took around %.2f seconds before introducer.furl was created.)'
                print tmpl % ((attempts + 1) * pollinterval,)
                shutil.copy(introfurl, self.clientbase)

                self.launch_client_layer()
                return # skip the timeout failure.

            else:
                time.sleep(pollinterval)

        tmpl = 'Timeout after waiting for creation of introducer.furl.\n'
        tmpl += 'Waited %.2f seconds (%d polls).'
        raise self.SetupFailure(tmpl, timeout, totalattempts)

    def launch_client_layer(self):
        print 'Launching client.'
        # NOTE: We assume if tahoe exist with non-zero status, no separate
        # tahoe child process is still running.
        output = self.run_tahoe('start', '--basedir', self.clientbase)
        try:
            pat = r'^STARTING (.*?)\nclient node probably started\s*$'
            self.check_tahoe_output(output, pat, self.clientbase)

            self.mount_fuse_layer()
            
        finally:
            print 'Stopping client node.'
            try:
                output = self.run_tahoe('stop', '--basedir', self.clientbase)
            except Exception, e:
                print 'Failed to stop client node.  Output:'
                print output
                print 'Ignoring cleanup exception: %r' % (e,)
        
    def mount_fuse_layer(self):
        # XXX not implemented.
        pass
        

    # Utilities:
    def run_tahoe(self, *args):
        realargs = ('tahoe',) + args
        status, output = gather_output(realargs, executable=self.cliexec)
        if status != 0:
            tmpl = 'The tahoe cli exited with nonzero status.\n'
            tmpl += 'Executable: %r\n'
            tmpl += 'Command arguments: %r\n'
            tmpl += 'Exit status: %r\n'
            tmpl += 'Output:\n%s\n[End of tahoe output.]\n'
            raise self.SetupFailure(tmpl,
                                    self.cliexec,
                                    realargs,
                                    status,
                                    output)
        return output
    
    def check_tahoe_output(self, output, expected, expdir):
        m = re.match(expected, output, re.M)
        if m is None:
            tmpl = 'The output of tahoe did not match the expectation:\n'
            tmpl += 'Expected regex: %s\n'
            tmpl += 'Actual output: %r\n'
            raise self.SetupFailure(tmpl, expected, output)

        if expdir != m.group(1):
            tmpl = 'The output of tahoe refers to an unexpected directory:\n'
            tmpl += 'Expected directory: %r\n'
            tmpl += 'Actual directory: %r\n'
            raise self.SetupFailure(tmpl, expdir, m.group(1))

    def cleanup_dir(self, path):
        try:
            shutil.rmtree(path)
        except Exception, e:
            print 'Exception removing test directory: %r' % (path,)
            print 'Ignoring cleanup exception: %r' % (e,)

    # SystemTest Exceptions:
    class Failure (Exception):
        pass
    
    class SetupFailure (Failure):
        def __init__(self, tmpl, *args):
            msg = 'SystemTest.SetupFailure - A test environment could not be created:\n'
            msg += tmpl % args
            SystemTest.Failure.__init__(self, msg)


### Unit Tests:
class TestUtilFunctions (unittest.TestCase):
    '''Tests small stand-alone functions.'''
    def test_canonicalize_cap(self):
        iopairs = [('http://127.0.0.1:8123/uri/URI:DIR2:yar9nnzsho6czczieeesc65sry:upp1pmypwxits3w9izkszgo1zbdnsyk3nm6h7e19s7os7s6yhh9y',
                    'URI:DIR2:yar9nnzsho6czczieeesc65sry:upp1pmypwxits3w9izkszgo1zbdnsyk3nm6h7e19s7os7s6yhh9y'),
                   ('http://127.0.0.1:8123/uri/URI%3ACHK%3Ak7ktp1qr7szmt98s1y3ha61d9w%3A8tiy8drttp65u79pjn7hs31po83e514zifdejidyeo1ee8nsqfyy%3A3%3A12%3A242?filename=welcome.html',
                    'URI:CHK:k7ktp1qr7szmt98s1y3ha61d9w:8tiy8drttp65u79pjn7hs31po83e514zifdejidyeo1ee8nsqfyy:3:12:242?filename=welcome.html')]

        for input, output in iopairs:
            result = tahoe_fuse.canonicalize_cap(input)
            self.failUnlessEqual(output, result, 'input == %r' % (input,))
                    


### Misc:
def gather_output(*args, **kwargs):
    '''
    This expects the child does not require input and that it closes
    stdout/err eventually.
    '''
    p = subprocess.Popen(stdout = subprocess.PIPE,
                         stderr = subprocess.STDOUT,
                         *args,
                         **kwargs)
    output = p.stdout.read()
    exitcode = p.wait()
    return (exitcode, output)
    
    
Usage = '''
Usage: %s [target]

Run tests for the given target.

target is one of: unit, system, or all
''' % (sys.argv[0],)



if __name__ == '__main__':
    main()
