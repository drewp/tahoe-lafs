"""
Decentralized storage grid.

community web site: U{http://tahoe-lafs.org/}
"""

# This is just to suppress DeprecationWarnings from nevow and twisted.
# See http://allmydata.org/trac/tahoe/ticket/859 and
# http://divmod.org/trac/ticket/2994 .
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning,
    message="the sha module is deprecated; use the hashlib module instead",
    append=True)
warnings.filterwarnings("ignore", category=DeprecationWarning,
    message="object.__new__\(\) takes no parameters",
    append=True)
warnings.filterwarnings("ignore", category=DeprecationWarning,
    message="The popen2 module is deprecated.  Use the subprocess module.",
    append=True)
warnings.filterwarnings("ignore", category=DeprecationWarning,
    message="the md5 module is deprecated; use hashlib instead",
    append=True)
warnings.filterwarnings("ignore", category=DeprecationWarning,
    message="twisted.web.error.NoResource is deprecated since Twisted 9.0.  See twisted.web.resource.NoResource.",
    append=True)
try:
    import nevow
    from twisted.persisted import sob
    from twisted.python import filepath
    hush_pyflakes = (nevow, sob, filepath)
    del hush_pyflakes
finally:
    warnings.filters.pop()
    warnings.filters.pop()
    warnings.filters.pop()
    warnings.filters.pop()
    # Don't pop the filter for the sha module warning because it is also generated
    # by pycrypto (which we don't want to import unless needed).
    # warnings.filters.pop()

# This warning is generated by twisted, PyRex, and possibly other packages,
# but can happen at any time, not only when they are imported. See
# http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1129 .
warnings.filterwarnings("ignore", category=DeprecationWarning,
    message="BaseException.message has been deprecated as of Python 2.6",
    append=True)

__version__ = "unknown"
try:
    from allmydata._version import __version__
except ImportError:
    # We're running in a tree that hasn't run "./setup.py darcsver", and didn't
    # come with a _version.py, so we don't know what our version is. This should
    # not happen very often.
    pass

__appname__ = "unknown"
try:
    from allmydata._appname import __appname__
except ImportError:
    # We're running in a tree that hasn't run "./setup.py".  This shouldn't happen.
    pass

# __full_version__ is the one that you ought to use when identifying yourself in the
# "application" part of the Tahoe versioning scheme:
# http://allmydata.org/trac/tahoe/wiki/Versioning
__full_version__ = __appname__ + '/' + str(__version__)

# Ideally we would call require_auto_deps() before importing nevow and twisted, but
# that causes midnightmagic's NetBSD buildslave to be unable to import allmydata.test,
# for reasons that are not understood. We want to call require_auto_deps() before other
# imports because the setuptools docs claim that if a distribution is installed with
# --multi-version, it might not importable until after pkg_resources.require()
# has been called for it. We don't have an example of this happening at this time.
# It is possible that require() isn't actually needed because we set __requires__
# in the generated startup script, but that would be an undocumented property of the
# setuptools implementation.

from allmydata import _auto_deps
_auto_deps.require_auto_deps()

import os, platform, re, subprocess, sys
_distributor_id_cmdline_re = re.compile("(?:Distributor ID:)\s*(.*)", re.I)
_release_cmdline_re = re.compile("(?:Release:)\s*(.*)", re.I)

_distributor_id_file_re = re.compile("(?:DISTRIB_ID\s*=)\s*(.*)", re.I)
_release_file_re = re.compile("(?:DISTRIB_RELEASE\s*=)\s*(.*)", re.I)

global _distname,_version
_distname = None
_version = None

def get_linux_distro():
    """ Tries to determine the name of the Linux OS distribution name.

    First, try to parse a file named "/etc/lsb-release".  If it exists, and
    contains the "DISTRIB_ID=" line and the "DISTRIB_RELEASE=" line, then return
    the strings parsed from that file.

    If that doesn't work, then invoke platform.dist().

    If that doesn't work, then try to execute "lsb_release", as standardized in
    2001:

    http://refspecs.freestandards.org/LSB_1.0.0/gLSB/lsbrelease.html

    The current version of the standard is here:

    http://refspecs.freestandards.org/LSB_3.2.0/LSB-Core-generic/LSB-Core-generic/lsbrelease.html

    that lsb_release emitted, as strings.

    Returns a tuple (distname,version). Distname is what LSB calls a
    "distributor id", e.g. "Ubuntu".  Version is what LSB calls a "release",
    e.g. "8.04".

    A version of this has been submitted to python as a patch for the standard
    library module "platform":

    http://bugs.python.org/issue3937
    """
    global _distname,_version
    if _distname and _version:
        return (_distname, _version)

    try:
        etclsbrel = open("/etc/lsb-release", "rU")
        for line in etclsbrel:
            m = _distributor_id_file_re.search(line)
            if m:
                _distname = m.group(1).strip()
                if _distname and _version:
                    return (_distname, _version)
            m = _release_file_re.search(line)
            if m:
                _version = m.group(1).strip()
                if _distname and _version:
                    return (_distname, _version)
    except EnvironmentError:
        pass

    (_distname, _version) = platform.dist()[:2]
    if _distname and _version:
        return (_distname, _version)

    try:
        p = subprocess.Popen(["lsb_release", "--all"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        rc = p.wait()
        if rc == 0:
            for line in p.stdout.readlines():
                m = _distributor_id_cmdline_re.search(line)
                if m:
                    _distname = m.group(1).strip()
                    if _distname and _version:
                        return (_distname, _version)

                m = _release_cmdline_re.search(p.stdout.read())
                if m:
                    _version = m.group(1).strip()
                    if _distname and _version:
                        return (_distname, _version)
    except EnvironmentError:
        pass

    if os.path.exists("/etc/arch-release"):
        return ("Arch_Linux", "")

    return (_distname,_version)

def get_platform():
    # Our version of platform.platform(), telling us both less and more than the
    # Python Standard Library's version does.
    # We omit details such as the Linux kernel version number, but we add a
    # more detailed and correct rendition of the Linux distribution and
    # distribution-version.
    if "linux" in platform.system().lower():
        return platform.system()+"-"+"_".join(get_linux_distro())+"-"+platform.machine()+"-"+"_".join([x for x in platform.architecture() if x])
    else:
        return platform.platform()

def get_package_versions_from_setuptools():
    import pkg_resources
    return dict([(p.project_name, (p.version, p.location)) for p in pkg_resources.require(__appname__)])

def package_dir(srcfile):
    return os.path.dirname(os.path.dirname(os.path.normcase(os.path.realpath(srcfile))))

def get_package_versions_and_locations():
    # because there are a few dependencies that are outside setuptools's ken
    # (Python and platform, and sqlite3 if you are on Python >= 2.5), and
    # because setuptools might fail to find something even though import
    # finds it:
    import OpenSSL, allmydata, foolscap.api, nevow, platform, pycryptopp, setuptools, simplejson, twisted, zfec, zope.interface
    pysqlitever = None
    pysqlitefile = None
    sqlitever = None
    try:
        import sqlite3
    except ImportError:
        try:
            from pysqlite2 import dbapi2
        except ImportError:
            pass
        else:
            pysqlitever = dbapi2.version
            pysqlitefile = package_dir(dbapi2.__file__)
            sqlitever = dbapi2.sqlite_version
    else:
        pysqlitever = sqlite3.version
        pysqlitefile = package_dir(sqlite3.__file__)
        sqlitever = sqlite3.sqlite_version

    d1 = {
        'pyOpenSSL': (OpenSSL.__version__, package_dir(OpenSSL.__file__)),
        __appname__: (allmydata.__version__, package_dir(allmydata.__file__)),
        'foolscap': (foolscap.api.__version__, package_dir(foolscap.__file__)),
        'Nevow': (nevow.__version__, package_dir(nevow.__file__)),
        'pycryptopp': (pycryptopp.__version__, package_dir(pycryptopp.__file__)),
        'setuptools': (setuptools.__version__, package_dir(setuptools.__file__)),
        'simplejson': (simplejson.__version__, package_dir(simplejson.__file__)),
        'pysqlite': (pysqlitever, pysqlitefile),
        'sqlite': (sqlitever, 'unknown'),
        'zope.interface': ('unknown', package_dir(zope.interface.__file__)),
        'Twisted': (twisted.__version__, package_dir(twisted.__file__)),
        'zfec': (zfec.__version__, package_dir(zfec.__file__)),
        'python': (platform.python_version(), sys.executable),
        'platform': (get_platform(), None),
        }

    # But we prefer to get all the dependencies as known by setuptools:
    import pkg_resources
    try:
        d2 = get_package_versions_from_setuptools()
    except pkg_resources.DistributionNotFound:
        # See docstring in _auto_deps.require_auto_deps() to explain why it makes sense to ignore this exception.
        pass
    else:
        d1.update(d2)

    return d1

def get_package_versions():
    return dict([(k, v) for k, (v, l) in get_package_versions_and_locations().iteritems()])

def get_package_locations():
    return dict([(k, l) for k, (v, l) in get_package_versions_and_locations().iteritems()])

def get_package_versions_string(show_paths=False):
    vers_and_locs = get_package_versions_and_locations()
    res = []
    for p in [__appname__, "foolscap", "pycryptopp", "zfec", "Twisted", "Nevow", "zope.interface", "python", "platform"]:
        (ver, loc) = vers_and_locs.get(p, ('UNKNOWN', 'UNKNOWN'))
        info = str(p) + ": " + str(ver)
        if show_paths:
            info = info + " (%s)" % str(loc)
        res.append(info)
        if vers_and_locs.has_key(p):
            del vers_and_locs[p]

    for p, (v, loc) in vers_and_locs.iteritems():
        info = str(p) + ": " + str(v)
        if show_paths:
            info = info + " (%s)" % str(loc)
        res.append(info)
    return ', '.join(res)
