﻿==================================
User-Visible Changes in Tahoe-LAFS
==================================

Release 1.9.0 (2011-??-??)
--------------------------

- The unmaintained FUSE plugins were removed from the source tree. See
  docs/frontends/FTP-and-SFTP.rst for how to use sshfs. (`#1409`_)
- Nodes now emit "None" for percentiles with higher implied precision
  than the number of observations can support. Older stats gatherers
  will throw an exception if they gather stats from a new storage
  server and it sends a "None" for a percentile. (`#1392`_)

Compatibility and Dependencies
''''''''''''''''''''''''''''''

- An incompatibility of zope.interface version 3.6.4 with Nevow has
  been resolved. Tahoe-LAFS now requires one of the exact versions
  v3.3.1, v3.5.3, or v3.6.1 of zope.interface. (`#1435`_)
- The Twisted dependency has been raised to version 10.1. This ensures
  that we no longer require pywin32 on Windows, and that it is never
  necessary to patch Twisted in order to use the FTP frontend.
  (`#1274`_, `#1438`_)

.. _`#1274`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1274
.. _`#1392`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1392
.. _`#1409`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1409
.. _`#1435`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1435
.. _`#1438`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1438


Release 1.8.2 (2011-01-30)
--------------------------

Compatibility and Dependencies
''''''''''''''''''''''''''''''

- Tahoe is now compatible with Twisted-10.2 (released last month), as
  well as with earlier versions. The previous Tahoe-1.8.1 release
  failed to run against Twisted-10.2, raising an AttributeError on
  StreamServerEndpointService (`#1286`_)
- Tahoe now depends upon the "mock" testing library, and the foolscap
  dependency was raised to 0.6.1 . It no longer requires pywin32
  (which was used only on windows). Future developers should note that
  reactor.spawnProcess and derivatives may no longer be used inside
  Tahoe code.

Other Changes
'''''''''''''

- the default reserved_space value for new storage nodes is 1 GB
  (`#1208`_)
- documentation is now in reStructuredText (.rst) format
- "tahoe cp" should now handle non-ASCII filenames
- the unmaintained Mac/Windows GUI applications have been removed
  (`#1282`_)
- tahoe processes should appear in top and ps as "tahoe", not
  "python", on some unix platforms. (`#174`_)
- "tahoe debug trial" can be used to run the test suite (`#1296`_)
- the SFTP frontend now reports unknown sizes as "0" instead of "?",
  to improve compatibility with clients like FileZilla (`#1337`_)
- "tahoe --version" should now report correct values in situations
  where 1.8.1 might have been wrong (`#1287`_)

.. _`#174`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/174
.. _`#1208`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1208
.. _`#1282`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1282
.. _`#1286`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1286
.. _`#1287`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1287
.. _`#1296`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1296
.. _`#1337`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1337


Release 1.8.1 (2010-10-28)
--------------------------

Bugfixes and Improvements
'''''''''''''''''''''''''

- Allow the repairer to improve the health of a file by uploading some
  shares, even if it cannot achieve the configured happiness
  threshold. This fixes a regression introduced between v1.7.1 and
  v1.8.0. (`#1212`_)
- Fix a memory leak in the ResponseCache which is used during mutable
  file/directory operations. (`#1045`_)
- Fix a regression and add a performance improvement in the
  downloader.  This issue caused repair to fail in some special
  cases. (`#1223`_)
- Fix a bug that caused 'tahoe cp' to fail for a grid-to-grid copy
  involving a non-ASCII filename. (`#1224`_)
- Fix a rarely-encountered bug involving printing large strings to the
  console on Windows. (`#1232`_)
- Perform ~ expansion in the --exclude-from filename argument to
  'tahoe backup'. (`#1241`_)
- The CLI's 'tahoe mv' and 'tahoe ln' commands previously would try to
  use an HTTP proxy if the HTTP_PROXY environment variable was set.
  These now always connect directly to the WAPI, thus avoiding giving
  caps to the HTTP proxy (and also avoiding failures in the case that
  the proxy is failing or requires authentication). (`#1253`_)
- The CLI now correctly reports failure in the case that 'tahoe mv'
  fails to unlink the file from its old location. (`#1255`_)
- 'tahoe start' now gives a more positive indication that the node has
  started. (`#71`_)
- The arguments seen by 'ps' or other tools for node processes are now
  more useful (in particular, they include the path of the 'tahoe'
  script, rather than an obscure tool named 'twistd'). (`#174`_)

Removed Features
''''''''''''''''

- The tahoe start/stop/restart and node creation commands no longer
  accept the -m or --multiple option, for consistency between
  platforms.  (`#1262`_)

Packaging
'''''''''

- We now host binary packages so that users on certain operating
  systems can install without having a compiler.
  <http://tahoe-lafs.org/source/tahoe-lafs/deps/tahoe-lafs-dep-eggs/README.html>
- Use a newer version of a dependency if needed, even if an older
  version is installed. This would previously cause a VersionConflict
  error. (`#1190`_)
- Use a precompiled binary of a dependency if one with a sufficiently
  high version number is available, instead of attempting to compile
  the dependency from source, even if the source version has a higher
  version number. (`#1233`_)

Documentation
'''''''''''''

- All current documentation in .txt format has been converted to .rst
  format. (`#1225`_)
- Added docs/backdoors.rst declaring that we won't add backdoors to
  Tahoe-LAFS, or add anything to facilitate government access to data.
  (`#1216`_)

.. _`#71`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/71
.. _`#174`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/174
.. _`#1212`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1212
.. _`#1045`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1045
.. _`#1190`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1190
.. _`#1216`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1216
.. _`#1223`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1223
.. _`#1224`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1224
.. _`#1225`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1225
.. _`#1232`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1232
.. _`#1233`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1233
.. _`#1241`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1241
.. _`#1253`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1253
.. _`#1255`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1255
.. _`#1262`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1262


Release 1.8.0 (2010-09-23)
--------------------------

New Features
''''''''''''

- A completely new downloader which improves performance and
  robustness of immutable-file downloads. It uses the fastest K
  servers to download the data in K-way parallel. It automatically
  fails over to alternate servers if servers fail in mid-download. It
  allows seeking to arbitrary locations in the file (the previous
  downloader which would only read the entire file sequentially from
  beginning to end). It minimizes unnecessary round trips and
  unnecessary bytes transferred to improve performance. It sends
  requests to fewer servers to reduce the load on servers (the
  previous one would send a small request to every server for every
  download) (`#287`_, `#288`_, `#448`_, `#798`_, `#800`_, `#990`_,
  `#1170`_, `#1191`_)
- Non-ASCII command-line arguments and non-ASCII outputs now work on
  Windows. In addition, the command-line tool now works on 64-bit
  Windows. (`#1074`_)

Bugfixes and Improvements
'''''''''''''''''''''''''

- Document and clean up the command-line options for specifying the
  node's base directory. (`#188`_, `#706`_, `#715`_, `#772`_,
  `#1108`_)
- The default node directory for Windows is ".tahoe" in the user's
  home directory, the same as on other platforms. (`#890`_)
- Fix a case in which full cap URIs could be logged. (`#685`_,
  `#1155`_)
- Fix bug in WUI in Python 2.5 when the system clock is set back to
  1969. Now you can use Tahoe-LAFS with Python 2.5 and set your system
  clock to 1969 and still use the WUI. (`#1055`_)
- Many improvements in code organization, tests, logging,
  documentation, and packaging. (`#983`_, `#1074`_, `#1108`_,
  `#1127`_, `#1129`_, `#1131`_, `#1166`_, `#1175`_)

Dependency Updates
''''''''''''''''''

- on x86 and x86-64 platforms, pycryptopp >= 0.5.20
- pycrypto 2.2 is excluded due to a bug

.. _`#188`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/188
.. _`#287`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/287
.. _`#288`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/288
.. _`#448`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/448
.. _`#685`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/685
.. _`#706`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/706
.. _`#715`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/715
.. _`#772`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/772
.. _`#798`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/798
.. _`#800`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/800
.. _`#890`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/890
.. _`#983`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/983
.. _`#990`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/990
.. _`#1055`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1055
.. _`#1074`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1074
.. _`#1108`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1108
.. _`#1155`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1155
.. _`#1170`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1170
.. _`#1191`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1191
.. _`#1127`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1127
.. _`#1129`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1129
.. _`#1131`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1131
.. _`#1166`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1166
.. _`#1175`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1175

Release 1.7.1 (2010-07-18)
--------------------------

Bugfixes and Improvements
'''''''''''''''''''''''''

- Fix bug in which uploader could fail with AssertionFailure or report
  that it had achieved servers-of-happiness when it hadn't. (`#1118`_)
- Fix bug in which servers could get into a state where they would
  refuse to accept shares of a certain file (`#1117`_)
- Add init scripts for managing the gateway server on Debian/Ubuntu
  (`#961`_)
- Fix bug where server version number was always 0 on the welcome page
  (`#1067`_)
- Add new command-line command "tahoe unlink" as a synonym for "tahoe
  rm" (`#776`_)
- The FTP frontend now encrypts its temporary files, protecting their
  contents from an attacker who is able to read the disk. (`#1083`_)
- Fix IP address detection on FreeBSD 7, 8, and 9 (`#1098`_)
- Fix minor layout issue in the Web User Interface with Internet
  Explorer (`#1097`_)
- Fix rarely-encountered incompatibility between Twisted logging
  utility and the new unicode support added in v1.7.0 (`#1099`_)
- Forward-compatibility improvements for non-ASCII caps (`#1051`_)

Code improvements
'''''''''''''''''

- Simplify and tidy-up directories, unicode support, test code
  (`#923`_, `#967`_, `#1072`_)

.. _`#776`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/776
.. _`#923`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/923
.. _`#961`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/961
.. _`#967`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/967
.. _`#1051`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1051
.. _`#1067`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1067
.. _`#1072`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1072
.. _`#1083`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1083
.. _`#1097`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1097
.. _`#1098`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1098
.. _`#1099`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1099
.. _`#1117`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1117
.. _`#1118`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1118


Release 1.7.0 (2010-06-18)
--------------------------

New Features
''''''''''''

- SFTP support (`#1037`_)
  Your Tahoe-LAFS gateway now acts like a full-fledged SFTP server. It
  has been tested with sshfs to provide a virtual filesystem in Linux.
  Many users have asked for this feature.  We hope that it serves them
  well! See the `FTP-and-SFTP.rst`_ document to get
  started.
- support for non-ASCII character encodings (`#534`_)
  Tahoe-LAFS now correctly handles filenames containing non-ASCII
  characters on all supported platforms:

 - when reading files in from the local filesystem (such as when you
   run "tahoe backup" to back up your local files to a Tahoe-LAFS
   grid);
 - when writing files out to the local filesystem (such as when you
   run "tahoe cp -r" to recursively copy files out of a Tahoe-LAFS
   grid);
 - when displaying filenames to the terminal (such as when you run
   "tahoe ls"), subject to limitations of the terminal and locale;
 - when parsing command-line arguments, except on Windows.

- Servers of Happiness (`#778`_)
  Tahoe-LAFS now measures during immutable file upload to see how well
  distributed it is across multiple servers. It aborts the upload if
  the pieces of the file are not sufficiently well-distributed.
  This behavior is controlled by a configuration parameter called
  "servers of happiness". With the default settings for its erasure
  coding, Tahoe-LAFS generates 10 shares for each file, such that any
  3 of those shares are sufficient to recover the file. The default
  value of "servers of happiness" is 7, which means that Tahoe-LAFS
  will guarantee that there are at least 7 servers holding some of the
  shares, such that any 3 of those servers can completely recover your
  file.  The new upload code also distributes the shares better than the
  previous version in some cases and takes better advantage of
  pre-existing shares (when a file has already been previously
  uploaded). See the `architecture.rst`_ document [3] for details.

Bugfixes and Improvements
'''''''''''''''''''''''''

- Premature abort of upload if some shares were already present and
  some servers fail. (`#608`_)
- python ./setup.py install -- can't create or remove files in install
  directory. (`#803`_)
- Network failure => internal TypeError. (`#902`_)
- Install of Tahoe on CentOS 5.4. (`#933`_)
- CLI option --node-url now supports https url. (`#1028`_)
- HTML/CSS template files were not correctly installed under
  Windows. (`#1033`_)
- MetadataSetter does not enforce restriction on setting "tahoe"
  subkeys.  (`#1034`_)
- ImportError: No module named
  setuptools_darcs.setuptools_darcs. (`#1054`_)
- Renamed Title in xhtml files. (`#1062`_)
- Increase Python version dependency to 2.4.4, to avoid a critical
  CPython security bug. (`#1066`_)
- Typo correction for the munin plugin tahoe_storagespace. (`#968`_)
- Fix warnings found by pylint. (`#973`_)
- Changing format of some documentation files. (`#1027`_)
- the misc/ directory was tied up. (`#1068`_)
- The 'ctime' and 'mtime' metadata fields are no longer written except
  by "tahoe backup". (`#924`_)
- Unicode filenames in Tahoe-LAFS directories are normalized so that
  names that differ only in how accents are encoded are treated as the
  same. (`#1076`_)
- Various small improvements to documentation. (`#937`_, `#911`_,
  `#1024`_, `#1082`_)

Removals
''''''''

- The 'tahoe debug consolidate' subcommand (for converting old
  allmydata Windows client backups to a newer format) has been
  removed.

Dependency Updates
''''''''''''''''''

- the Python version dependency is raised to 2.4.4 in some cases
  (2.4.3 for Redhat-based Linux distributions, 2.4.2 for UCS-2 builds)
  (`#1066`_)
- pycrypto >= 2.0.1
- pyasn1 >= 0.0.8a
- mock (only required by unit tests)

.. _`#534`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/534
.. _`#608`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/608
.. _`#778`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/778
.. _`#803`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/803
.. _`#902`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/902
.. _`#911`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/911
.. _`#924`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/924
.. _`#937`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/937
.. _`#933`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/933
.. _`#968`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/968
.. _`#973`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/973
.. _`#1024`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1024
.. _`#1027`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1027
.. _`#1028`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1028
.. _`#1033`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1033
.. _`#1034`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1034
.. _`#1037`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1037
.. _`#1054`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1054
.. _`#1062`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1062
.. _`#1066`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1066
.. _`#1068`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1068
.. _`#1076`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1076
.. _`#1082`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/1082
.. _architecture.rst: docs/architecture.rst
.. _FTP-and-SFTP.rst: docs/frontends/FTP-and-SFTP.rst

Release 1.6.1 (2010-02-27)
--------------------------

Bugfixes
''''''''

- Correct handling of Small Immutable Directories

  Immutable directories can now be deep-checked and listed in the web
  UI in all cases. (In v1.6.0, some operations, such as deep-check, on
  a directory graph that included very small immutable directories,
  would result in an exception causing the whole operation to abort.)
  (`#948`_)

Usability Improvements
''''''''''''''''''''''

- Improved user interface messages and error reporting. (`#681`_,
  `#837`_, `#939`_)
- The timeouts for operation handles have been greatly increased, so
  that you can view the results of an operation up to 4 days after it
  has completed. After viewing them for the first time, the results
  are retained for a further day. (`#577`_)

Release 1.6.0 (2010-02-01)
--------------------------

New Features
''''''''''''

- Immutable Directories

  Tahoe-LAFS can now create and handle immutable
  directories. (`#607`_, `#833`_, `#931`_) These are read just like
  normal directories, but are "deep-immutable", meaning that all their
  children (and everything reachable from those children) must be
  immutable objects (i.e. immutable or literal files, and other
  immutable directories).

  These directories must be created in a single webapi call that
  provides all of the children at once. (Since they cannot be changed
  after creation, the usual create/add/add sequence cannot be used.)
  They have URIs that start with "URI:DIR2-CHK:" or "URI:DIR2-LIT:",
  and are described on the human-facing web interface (aka the "WUI")
  with a "DIR-IMM" abbreviation (as opposed to "DIR" for the usual
  read-write directories and "DIR-RO" for read-only directories).

  Tahoe-LAFS releases before 1.6.0 cannot read the contents of an
  immutable directory. 1.5.0 will tolerate their presence in a
  directory listing (and display it as "unknown"). 1.4.1 and earlier
  cannot tolerate them: a DIR-IMM child in any directory will prevent
  the listing of that directory.

  Immutable directories are repairable, just like normal immutable
  files.

  The webapi "POST t=mkdir-immutable" call is used to create immutable
  directories. See `webapi.rst`_ for details.

- "tahoe backup" now creates immutable directories, backupdb has
  dircache

  The "tahoe backup" command has been enhanced to create immutable
  directories (in previous releases, it created read-only mutable
  directories) (`#828`_). This is significantly faster, since it does
  not need to create an RSA keypair for each new directory. Also
  "DIR-IMM" immutable directories are repairable, unlike "DIR-RO"
  read-only mutable directories at present. (A future Tahoe-LAFS
  release should also be able to repair DIR-RO.)

  In addition, the backupdb (used by "tahoe backup" to remember what
  it has already copied) has been enhanced to store information about
  existing immutable directories. This allows it to re-use directories
  that have moved but still contain identical contents, or that have
  been deleted and later replaced. (The 1.5.0 "tahoe backup" command
  could only re-use directories that were in the same place as they
  were in the immediately previous backup.)  With this change, the
  backup process no longer needs to read the previous snapshot out of
  the Tahoe-LAFS grid, reducing the network load
  considerably. (`#606`_)

  A "null backup" (in which nothing has changed since the previous
  backup) will require only two Tahoe-side operations: one to add an
  Archives/$TIMESTAMP entry, and a second to update the Latest/
  link. On the local disk side, it will readdir() all your local
  directories and stat() all your local files.

  If you've been using "tahoe backup" for a while, you will notice
  that your first use of it after upgrading to 1.6.0 may take a long
  time: it must create proper immutable versions of all the old
  read-only mutable directories. This process won't take as long as
  the initial backup (where all the file contents had to be uploaded
  too): it will require time proportional to the number and size of
  your directories. After this initial pass, all subsequent passes
  should take a tiny fraction of the time.

  As noted above, Tahoe-LAFS versions earlier than 1.5.0 cannot list a
  directory containing an immutable subdirectory. Tahoe-LAFS versions
  earlier than 1.6.0 cannot read the contents of an immutable
  directory.

  The "tahoe backup" command has been improved to skip over unreadable
  objects (like device files, named pipes, and files with permissions
  that prevent the command from reading their contents), instead of
  throwing an exception and terminating the backup process. It also
  skips over symlinks, because these cannot be represented faithfully
  in the Tahoe-side filesystem. A warning message will be emitted each
  time something is skipped. (`#729`_, `#850`_, `#641`_)

- "create-node" command added, "create-client" now implies
  --no-storage

  The basic idea behind Tahoe-LAFS's client+server and client-only
  processes is that you are creating a general-purpose Tahoe-LAFS
  "node" process, which has several components that can be
  activated. Storage service is one of these optional components, as
  is the Helper, FTP server, and SFTP server. Web gateway
  functionality is nominally on this list, but it is always active; a
  future release will make it optional. There are three special
  purpose servers that can't currently be run as a component in a
  node: introducer, key-generator, and stats-gatherer.

  So now "tahoe create-node" will create a Tahoe-LAFS node process,
  and after creation you can edit its tahoe.cfg to enable or disable
  the desired services. It is a more general-purpose replacement for
  "tahoe create-client".  The default configuration has storage
  service enabled. For convenience, the "--no-storage" argument makes
  a tahoe.cfg file that disables storage service. (`#760`_)

  "tahoe create-client" has been changed to create a Tahoe-LAFS node
  without a storage service. It is equivalent to "tahoe create-node
  --no-storage". This helps to reduce the confusion surrounding the
  use of a command with "client" in its name to create a storage
  *server*. Use "tahoe create-client" to create a purely client-side
  node. If you want to offer storage to the grid, use "tahoe
  create-node" instead.

  In the future, other services will be added to the node, and they
  will be controlled through options in tahoe.cfg . The most important
  of these services may get additional --enable-XYZ or --disable-XYZ
  arguments to "tahoe create-node".

- Performance Improvements

  Download of immutable files begins as soon as the downloader has
  located the K necessary shares (`#928`_, `#287`_). In both the
  previous and current releases, a downloader will first issue queries
  to all storage servers on the grid to locate shares before it begins
  downloading the shares. In previous releases of Tahoe-LAFS, download
  would not begin until all storage servers on the grid had replied to
  the query, at which point K shares would be chosen for download from
  among the shares that were located. In this release, download begins
  as soon as any K shares are located. This means that downloads start
  sooner, which is particularly important if there is a server on the
  grid that is extremely slow or even hung in such a way that it will
  never respond. In previous releases such a server would have a
  negative impact on all downloads from that grid. In this release,
  such a server will have no impact on downloads, as long as K shares
  can be found on other, quicker, servers.  This also means that
  downloads now use the "best-alacrity" servers that they talk to, as
  measured by how quickly the servers reply to the initial query. This
  might cause downloads to go faster, especially on grids with
  heterogeneous servers or geographical dispersion.

Minor Changes
'''''''''''''

- The webapi acquired a new "t=mkdir-with-children" command, to create
  and populate a directory in a single call. This is significantly
  faster than using separate "t=mkdir" and "t=set-children" operations
  (it uses one gateway-to-grid roundtrip, instead of three or
  four). (`#533`_)

- The t=set-children (note the hyphen) operation is now documented in
  webapi.rst, and is the new preferred spelling of the
  old t=set_children (with an underscore). The underscore version
  remains for backwards compatibility. (`#381`_, `#927`_)

- The tracebacks produced by errors in CLI tools should now be in
  plain text, instead of HTML (which is unreadable outside of a
  browser). (`#646`_)

- The [storage]reserved_space configuration knob (which causes the
  storage server to refuse shares when available disk space drops
  below a threshold) should work on Windows now, not just
  UNIX. (`#637`_)

- "tahoe cp" should now exit with status "1" if it cannot figure out a
  suitable target filename, such as when you copy from a bare
  filecap. (`#761`_)

- "tahoe get" no longer creates a zero-length file upon
  error. (`#121`_)

- "tahoe ls" can now list single files. (`#457`_)

- "tahoe deep-check --repair" should tolerate repair failures now,
  instead of halting traversal. (`#874`_, `#786`_)

- "tahoe create-alias" no longer corrupts the aliases file if it had
  previously been edited to have no trailing newline. (`#741`_)

- Many small packaging improvements were made to facilitate the
  "tahoe-lafs" package being included in Ubuntu. Several mac/win32
  binary libraries were removed, some figleaf code-coverage files were
  removed, a bundled copy of darcsver-1.2.1 was removed, and
  additional licensing text was added.

- Several DeprecationWarnings for python2.6 were silenced. (`#859`_)

- The checker --add-lease option would sometimes fail for shares
  stored on old (Tahoe v1.2.0) servers. (`#875`_)

- The documentation for installing on Windows (docs/quickstart.rst)
  has been improved. (`#773`_)

For other changes not mentioned here, see
<http://tahoe-lafs.org/trac/tahoe/query?milestone=1.6.0&keywords=!~news-done>.
To include the tickets mentioned above, go to
<http://tahoe-lafs.org/trac/tahoe/query?milestone=1.6.0>.

.. _`#121`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/121
.. _`#287`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/287
.. _`#381`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/381
.. _`#457`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/457
.. _`#533`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/533
.. _`#577`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/577
.. _`#606`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/606
.. _`#607`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/607
.. _`#637`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/637
.. _`#641`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/641
.. _`#646`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/646
.. _`#681`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/681
.. _`#729`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/729
.. _`#741`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/741
.. _`#760`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/760
.. _`#761`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/761
.. _`#768`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/768
.. _`#773`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/773
.. _`#786`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/786
.. _`#828`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/828
.. _`#833`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/833
.. _`#859`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/859
.. _`#874`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/874
.. _`#875`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/875
.. _`#931`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/931
.. _`#837`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/837
.. _`#850`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/850
.. _`#927`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/927
.. _`#928`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/928
.. _`#939`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/939
.. _`#948`: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/948
.. _webapi.rst: docs/frontends/webapi.rst

Release 1.5.0 (2009-08-01)
--------------------------

Improvements
''''''''''''

- Uploads of immutable files now use pipelined writes, improving
  upload speed slightly (10%) over high-latency connections. (`#392`_)

- Processing large directories has been sped up, by removing a O(N^2)
  algorithm from the dirnode decoding path and retaining unmodified
  encrypted entries.  (`#750`_, `#752`_)

- The human-facing web interface (aka the "WUI") received a
  significant CSS makeover by Kevin Reid, making it much prettier and
  easier to read. The WUI "check" and "deep-check" forms now include a
  "Renew Lease" checkbox, mirroring the CLI --add-lease option, so
  leases can be added or renewed from the web interface.

- The CLI "tahoe mv" command now refuses to overwrite
  directories. (`#705`_)

- The CLI "tahoe webopen" command, when run without arguments, will
  now bring up the "Welcome Page" (node status and mkdir/upload
  forms).

- The 3.5MB limit on mutable files was removed, so it should be
  possible to upload arbitrarily-sized mutable files. Note, however,
  that the data format and algorithm remains the same, so using
  mutable files still requires bandwidth, computation, and RAM in
  proportion to the size of the mutable file.  (`#694`_)

- This version of Tahoe-LAFS will tolerate directory entries that
  contain filecap formats which it does not recognize: files and
  directories from the future.  This should improve the user
  experience (for 1.5.0 users) when we add new cap formats in the
  future. Previous versions would fail badly, preventing the user from
  seeing or editing anything else in those directories. These
  unrecognized objects can be renamed and deleted, but obviously not
  read or written. Also they cannot generally be copied. (`#683`_)

Bugfixes
''''''''

- deep-check-and-repair now tolerates read-only directories, such as
  the ones produced by the "tahoe backup" CLI command. Read-only
  directories and mutable files are checked, but not
  repaired. Previous versions threw an exception when attempting the
  repair and failed to process the remaining contents. We cannot yet
  repair these read-only objects, but at least this version allows the
  rest of the check+repair to proceed. (`#625`_)

- A bug in 1.4.1 which caused a server to be listed multiple times
  (and frequently broke all connections to that server) was
  fixed. (`#653`_)

- The plaintext-hashing code was removed from the Helper interface,
  removing the Helper's ability to mount a
  partial-information-guessing attack. (`#722`_)

Platform/packaging changes
''''''''''''''''''''''''''

- Tahoe-LAFS now runs on NetBSD, OpenBSD, ArchLinux, and NixOS, and on
  an embedded system based on an ARM CPU running at 266 MHz.

- Unit test timeouts have been raised to allow the tests to complete
  on extremely slow platforms like embedded ARM-based NAS boxes, which
  may take several hours to run the test suite. An ARM-specific
  data-corrupting bug in an older version of Crypto++ (5.5.2) was
  identified: ARM-users are encouraged to use recent
  Crypto++/pycryptopp which avoids this problem.

- Tahoe-LAFS now requires a SQLite library, either the sqlite3 that
  comes built-in with python2.5/2.6, or the add-on pysqlite2 if you're
  using python2.4. In the previous release, this was only needed for
  the "tahoe backup" command: now it is mandatory.

- Several minor documentation updates were made.

- To help get Tahoe-LAFS into Linux distributions like Fedora and
  Debian, packaging improvements are being made in both Tahoe-LAFS and
  related libraries like pycryptopp and zfec.

- The Crypto++ library included in the pycryptopp package has been
  upgraded to version 5.6.0 of Crypto++, which includes a more
  efficient implementation of SHA-256 in assembly for x86 or amd64
  architectures.

dependency updates
''''''''''''''''''

- foolscap-0.4.1
- no python-2.4.0 or 2.4.1 (2.4.2 is good) (they contained a bug in base64.b32decode)
- avoid python-2.6 on windows with mingw: compiler issues
- python2.4 requires pysqlite2 (2.5,2.6 does not)
- no python-3.x
- pycryptopp-0.5.15

.. _#392: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/392
.. _#625: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/625
.. _#653: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/653
.. _#683: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/683
.. _#694: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/694
.. _#705: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/705
.. _#722: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/722
.. _#750: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/750
.. _#752: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/752

Release 1.4.1 (2009-04-13)
--------------------------

Garbage Collection
''''''''''''''''''

- The big feature for this release is the implementation of garbage
  collection, allowing Tahoe storage servers to delete shares for old
  deleted files. When enabled, this uses a "mark and sweep" process:
  clients are responsible for updating the leases on their shares
  (generally by running "tahoe deep-check --add-lease"), and servers
  are allowed to delete any share which does not have an up-to-date
  lease. The process is described in detail in
  `garbage-collection.rst`_.

  The server must be configured to enable garbage-collection, by
  adding directives to the [storage] section that define an age limit
  for shares. The default configuration will not delete any shares.

  Both servers and clients should be upgraded to this release to make
  the garbage-collection as pleasant as possible. 1.2.0 servers have
  code to perform the update-lease operation but it suffers from a
  fatal bug, while 1.3.0 servers have update-lease but will return an
  exception for unknown storage indices, causing clients to emit an
  Incident for each exception, slowing the add-lease process down to a
  crawl. 1.1.0 servers did not have the add-lease operation at all.

Security/Usability Problems Fixed
'''''''''''''''''''''''''''''''''

- A super-linear algorithm in the Merkle Tree code was fixed, which
  previously caused e.g. download of a 10GB file to take several hours
  before the first byte of plaintext could be produced. The new
  "alacrity" is about 2 minutes. A future release should reduce this
  to a few seconds by fixing ticket `#442`_.

- The previous version permitted a small timing attack (due to our use
  of strcmp) against the write-enabler and lease-renewal/cancel
  secrets. An attacker who could measure response-time variations of
  approximatly 3ns against a very noisy background time of about 15ms
  might be able to guess these secrets. We do not believe this attack
  was actually feasible. This release closes the attack by first
  hashing the two strings to be compared with a random secret.

webapi changes
''''''''''''''

- In most cases, HTML tracebacks will only be sent if an "Accept:
  text/html" header was provided with the HTTP request. This will
  generally cause browsers to get an HTMLized traceback but send
  regular text/plain tracebacks to non-browsers (like the CLI
  clients). More errors have been mapped to useful HTTP error codes.

- The streaming webapi operations (deep-check and manifest) now have a
  way to indicate errors (an output line that starts with "ERROR"
  instead of being legal JSON). See `webapi.rst`_ for
  details.

- The storage server now has its own status page (at /storage), linked
  from the Welcome page. This page shows progress and results of the
  two new share-crawlers: one which merely counts shares (to give an
  estimate of how many files/directories are being stored in the
  grid), the other examines leases and reports how much space would be
  freed if GC were enabled. The page also shows how much disk space is
  present, used, reserved, and available for the Tahoe server, and
  whether the server is currently running in "read-write" mode or
  "read-only" mode.

- When a directory node cannot be read (perhaps because of insufficent
  shares), a minimal webapi page is created so that the "more-info"
  links (including a Check/Repair operation) will still be accessible.

- A new "reliability" page was added, with the beginnings of work on a
  statistical loss model. You can tell this page how many servers you
  are using and their independent failure probabilities, and it will
  tell you the likelihood that an arbitrary file will survive each
  repair period. The "numpy" package must be installed to access this
  page. A partial paper, written by Shawn Willden, has been added to
  docs/proposed/lossmodel.lyx .

CLI changes
'''''''''''

- "tahoe check" and "tahoe deep-check" now accept an "--add-lease"
  argument, to update a lease on all shares. This is the "mark" side
  of garbage collection.

- In many cases, CLI error messages have been improved: the ugly
  HTMLized traceback has been replaced by a normal python traceback.

- "tahoe deep-check" and "tahoe manifest" now have better error
  reporting.  "tahoe cp" is now non-verbose by default.

- "tahoe backup" now accepts several "--exclude" arguments, to ignore
  certain files (like editor temporary files and version-control
  metadata) during backup.

- On windows, the CLI now accepts local paths like "c:\dir\file.txt",
  which previously was interpreted as a Tahoe path using a "c:" alias.

- The "tahoe restart" command now uses "--force" by default (meaning
  it will start a node even if it didn't look like there was one
  already running).

- The "tahoe debug consolidate" command was added. This takes a series
  of independent timestamped snapshot directories (such as those
  created by the allmydata.com windows backup program, or a series of
  "tahoe cp -r" commands) and creates new snapshots that used shared
  read-only directories whenever possible (like the output of "tahoe
  backup"). In the most common case (when the snapshots are fairly
  similar), the result will use significantly fewer directories than
  the original, allowing "deep-check" and similar tools to run much
  faster. In some cases, the speedup can be an order of magnitude or
  more.  This tool is still somewhat experimental, and only needs to
  be run on large backups produced by something other than "tahoe
  backup", so it was placed under the "debug" category.

- "tahoe cp -r --caps-only tahoe:dir localdir" is a diagnostic tool
  which, instead of copying the full contents of files into the local
  directory, merely copies their filecaps. This can be used to verify
  the results of a "consolidation" operation.

other fixes
'''''''''''

- The codebase no longer rauses RuntimeError as a kind of
  assert(). Specific exception classes were created for each previous
  instance of RuntimeError.

 -Many unit tests were changed to use a non-network test harness,
  speeding them up considerably.

- Deep-traversal operations (manifest and deep-check) now walk
  individual directories in alphabetical order. Occasional turn breaks
  are inserted to prevent a stack overflow when traversing directories
  with hundreds of entries.

- The experimental SFTP server had its path-handling logic changed
  slightly, to accomodate more SFTP clients, although there are still
  issues (`#645`_).

.. _#442: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/442
.. _#645: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/645
.. _garbage-collection.rst: docs/garbage-collection.rst

Release 1.3.0 (2009-02-13)
--------------------------

Checker/Verifier/Repairer
'''''''''''''''''''''''''

- The primary focus of this release has been writing a checker /
  verifier / repairer for files and directories.  "Checking" is the
  act of asking storage servers whether they have a share for the
  given file or directory: if there are not enough shares available,
  the file or directory will be unrecoverable. "Verifying" is the act
  of downloading and cryptographically asserting that the server's
  share is undamaged: it requires more work (bandwidth and CPU) than
  checking, but can catch problems that simple checking
  cannot. "Repair" is the act of replacing missing or damaged shares
  with new ones.

- This release includes a full checker, a partial verifier, and a
  partial repairer. The repairer is able to handle missing shares: new
  shares are generated and uploaded to make up for the missing
  ones. This is currently the best application of the repairer: to
  replace shares that were lost because of server departure or
  permanent drive failure.

- The repairer in this release is somewhat able to handle corrupted
  shares. The limitations are:

 - Immutable verifier is incomplete: not all shares are used, and not
   all fields of those shares are verified. Therefore the immutable
   verifier has only a moderate chance of detecting corrupted shares.
 - The mutable verifier is mostly complete: all shares are examined,
   and most fields of the shares are validated.
 - The storage server protocol offers no way for the repairer to
   replace or delete immutable shares. If corruption is detected, the
   repairer will upload replacement shares to other servers, but the
   corrupted shares will be left in place.
 - read-only directories and read-only mutable files must be repaired
   by someone who holds the write-cap: the read-cap is
   insufficient. Moreover, the deep-check-and-repair operation will
   halt with an error if it attempts to repair one of these read-only
   objects.
 - Some forms of corruption can cause both download and repair
   operations to fail. A future release will fix this, since download
   should be tolerant of any corruption as long as there are at least
   'k' valid shares, and repair should be able to fix any file that is
   downloadable.

- If the downloader, verifier, or repairer detects share corruption,
  the servers which provided the bad shares will be notified (via a
  file placed in the BASEDIR/storage/corruption-advisories directory)
  so their operators can manually delete the corrupted shares and
  investigate the problem. In addition, the "incident gatherer"
  mechanism will automatically report share corruption to an incident
  gatherer service, if one is configured. Note that corrupted shares
  indicate hardware failures, serious software bugs, or malice on the
  part of the storage server operator, so a corrupted share should be
  considered highly unusual.

- By periodically checking/repairing all files and directories,
  objects in the Tahoe filesystem remain resistant to recoverability
  failures due to missing and/or broken servers.

- This release includes a wapi mechanism to initiate checks on
  individual files and directories (with or without verification, and
  with or without automatic repair). A related mechanism is used to
  initiate a "deep-check" on a directory: recursively traversing the
  directory and its children, checking (and/or verifying/repairing)
  everything underneath. Both mechanisms can be run with an
  "output=JSON" argument, to obtain machine-readable check/repair
  status results. These results include a copy of the filesystem
  statistics from the "deep-stats" operation (including total number
  of files, size histogram, etc). If repair is possible, a "Repair"
  button will appear on the results page.

- The client web interface now features some extra buttons to initiate
  check and deep-check operations. When these operations finish, they
  display a results page that summarizes any problems that were
  encountered. All long-running deep-traversal operations, including
  deep-check, use a start-and-poll mechanism, to avoid depending upon
  a single long-lived HTTP connection. `webapi.rst`_ has
  details.

Efficient Backup
''''''''''''''''

- The "tahoe backup" command is new in this release, which creates
  efficient versioned backups of a local directory. Given a local
  pathname and a target Tahoe directory, this will create a read-only
  snapshot of the local directory in $target/Archives/$timestamp. It
  will also create $target/Latest, which is a reference to the latest
  such snapshot. Each time you run "tahoe backup" with the same source
  and target, a new $timestamp snapshot will be added. These snapshots
  will share directories that have not changed since the last backup,
  to speed up the process and minimize storage requirements. In
  addition, a small database is used to keep track of which local
  files have been uploaded already, to avoid uploading them a second
  time. This drastically reduces the work needed to do a "null backup"
  (when nothing has changed locally), making "tahoe backup' suitable
  to run from a daily cronjob.

  Note that the "tahoe backup" CLI command must be used in conjunction
  with a 1.3.0-or-newer Tahoe client node; there was a bug in the
  1.2.0 webapi implementation that would prevent the last step (create
  $target/Latest) from working.

Large Files
'''''''''''

- The 12GiB (approximate) immutable-file-size limitation is
  lifted. This release knows how to handle so-called "v2 immutable
  shares", which permit immutable files of up to about 18 EiB (about
  3*10^14). These v2 shares are created if the file to be uploaded is
  too large to fit into v1 shares. v1 shares are created if the file
  is small enough to fit into them, so that files created with
  tahoe-1.3.0 can still be read by earlier versions if they are not
  too large. Note that storage servers also had to be changed to
  support larger files, and this release is the first release in which
  they are able to do that. Clients will detect which servers are
  capable of supporting large files on upload and will not attempt to
  upload shares of a large file to a server which doesn't support it.

FTP/SFTP Server
'''''''''''''''

- Tahoe now includes experimental FTP and SFTP servers. When
  configured with a suitable method to translate username+password
  into a root directory cap, it provides simple access to the virtual
  filesystem. Remember that FTP is completely unencrypted: passwords,
  filenames, and file contents are all sent over the wire in
  cleartext, so FTP should only be used on a local (127.0.0.1)
  connection. This feature is still in development: there are no unit
  tests yet, and behavior with respect to Unicode filenames is
  uncertain. Please see `FTP-and-SFTP.rst`_ for
  configuration details. (`#512`_, `#531`_)

CLI Changes
'''''''''''

- This release adds the 'tahoe create-alias' command, which is a
  combination of 'tahoe mkdir' and 'tahoe add-alias'. This also allows
  you to start using a new tahoe directory without exposing its URI in
  the argv list, which is publicly visible (through the process table)
  on most unix systems.  Thanks to Kevin Reid for bringing this issue
  to our attention.

- The single-argument form of "tahoe put" was changed to create an
  unlinked file. I.e. "tahoe put bar.txt" will take the contents of a
  local "bar.txt" file, upload them to the grid, and print the
  resulting read-cap; the file will not be attached to any
  directories. This seemed a bit more useful than the previous
  behavior (copy stdin, upload to the grid, attach the resulting file
  into your default tahoe: alias in a child named 'bar.txt').

- "tahoe put" was also fixed to handle mutable files correctly: "tahoe
  put bar.txt URI:SSK:..." will read the contents of the local bar.txt
  and use them to replace the contents of the given mutable file.

- The "tahoe webopen" command was modified to accept aliases. This
  means "tahoe webopen tahoe:" will cause your web browser to open to
  a "wui" page that gives access to the directory associated with the
  default "tahoe:" alias. It should also accept leading slashes, like
  "tahoe webopen tahoe:/stuff".

- Many esoteric debugging commands were moved down into a "debug"
  subcommand:

 - tahoe debug dump-cap
 - tahoe debug dump-share
 - tahoe debug find-shares
 - tahoe debug catalog-shares
 - tahoe debug corrupt-share

   The last command ("tahoe debug corrupt-share") flips a random bit
   of the given local sharefile. This is used to test the file
   verifying/repairing code, and obviously should not be used on user
   data.

The cli might not correctly handle arguments which contain non-ascii
characters in Tahoe v1.3 (although depending on your platform it
might, especially if your platform can be configured to pass such
characters on the command-line in utf-8 encoding).  See
http://tahoe-lafs.org/trac/tahoe/ticket/565 for details.

Web changes
'''''''''''

- The "default webapi port", used when creating a new client node (and
  in the getting-started documentation), was changed from 8123 to
  3456, to reduce confusion when Tahoe accessed through a Firefox
  browser on which the "Torbutton" extension has been installed. Port
  8123 is occasionally used as a Tor control port, so Torbutton adds
  8123 to Firefox's list of "banned ports" to avoid CSRF attacks
  against Tor. Once 8123 is banned, it is difficult to diagnose why
  you can no longer reach a Tahoe node, so the Tahoe default was
  changed. Note that 3456 is reserved by IANA for the "vat" protocol,
  but there are argueably more Torbutton+Tahoe users than vat users
  these days. Note that this will only affect newly-created client
  nodes. Pre-existing client nodes, created by earlier versions of
  tahoe, may still be listening on 8123.

- All deep-traversal operations (start-manifest, start-deep-size,
  start-deep-stats, start-deep-check) now use a start-and-poll
  approach, instead of using a single (fragile) long-running
  synchronous HTTP connection. All these "start-" operations use POST
  instead of GET. The old "GET manifest", "GET deep-size", and "POST
  deep-check" operations have been removed.

- The new "POST start-manifest" operation, when it finally completes,
  results in a table of (path,cap), instead of the list of verifycaps
  produced by the old "GET manifest". The table is available in
  several formats: use output=html, output=text, or output=json to
  choose one. The JSON output also includes stats, and a list of
  verifycaps and storage-index strings. The "return_to=" and
  "when_done=" arguments have been removed from the t=check and
  deep-check operations.

- The top-level status page (/status) now has a machine-readable form,
  via "/status/?t=json". This includes information about the
  currently-active uploads and downloads, which may be useful for
  frontends that wish to display progress information. There is no
  easy way to correlate the activities displayed here with recent wapi
  requests, however.

- Any files in BASEDIR/public_html/ (configurable) will be served in
  response to requests in the /static/ portion of the URL space. This
  will simplify the deployment of javascript-based frontends that can
  still access wapi calls by conforming to the (regrettable)
  "same-origin policy".

- The welcome page now has a "Report Incident" button, which is tied
  into the "Incident Gatherer" machinery. If the node is attached to
  an incident gatherer (via log_gatherer.furl), then pushing this
  button will cause an Incident to be signalled: this means recent log
  events are aggregated and sent in a bundle to the gatherer. The user
  can push this button after something strange takes place (and they
  can provide a short message to go along with it), and the relevant
  data will be delivered to a centralized incident-gatherer for later
  processing by operations staff.

- The "HEAD" method should now work correctly, in addition to the
  usual "GET", "PUT", and "POST" methods. "HEAD" is supposed to return
  exactly the same headers as "GET" would, but without any of the
  actual response body data. For mutable files, this now does a brief
  mapupdate (to figure out the size of the file that would be
  returned), without actually retrieving the file's contents.

- The "GET" operation on files can now support the HTTP "Range:"
  header, allowing requests for partial content. This allows certain
  media players to correctly stream audio and movies out of a Tahoe
  grid. The current implementation uses a disk-based cache in
  BASEDIR/private/cache/download , which holds the plaintext of the
  files being downloaded. Future implementations might not use this
  cache. GET for immutable files now returns an ETag header.

- Each file and directory now has a "Show More Info" web page, which
  contains much of the information that was crammed into the directory
  page before. This includes readonly URIs, storage index strings,
  object type, buttons to control checking/verifying/repairing, and
  deep-check/deep-stats buttons (for directories). For mutable files,
  the "replace contents" upload form has been moved here too. As a
  result, the directory page is now much simpler and cleaner, and
  several potentially-misleading links (like t=uri) are now gone.

- Slashes are discouraged in Tahoe file/directory names, since they
  cause problems when accessing the filesystem through the
  wapi. However, there are a couple of accidental ways to generate
  such names. This release tries to make it easier to correct such
  mistakes by escaping slashes in several places, allowing slashes in
  the t=info and t=delete commands, and in the source (but not the
  target) of a t=rename command.

Packaging
'''''''''

- Tahoe's dependencies have been extended to require the
  "[secure_connections]" feature from Foolscap, which will cause
  pyOpenSSL to be required and/or installed. If OpenSSL and its
  development headers are already installed on your system, this can
  occur automatically. Tahoe now uses pollreactor (instead of the
  default selectreactor) to work around a bug between pyOpenSSL and
  the most recent release of Twisted (8.1.0). This bug only affects
  unit tests (hang during shutdown), and should not impact regular
  use.

- The Tahoe source code tarballs now come in two different forms:
  regular and "sumo". The regular tarball contains just Tahoe, nothing
  else. When building from the regular tarball, the build process will
  download any unmet dependencies from the internet (starting with the
  index at PyPI) so it can build and install them. The "sumo" tarball
  contains copies of all the libraries that Tahoe requires (foolscap,
  twisted, zfec, etc), so using the "sumo" tarball should not require
  any internet access during the build process. This can be useful if
  you want to build Tahoe while on an airplane, a desert island, or
  other bandwidth-limited environments.

- Similarly, tahoe-lafs.org now hosts a "tahoe-deps" tarball which
  contains the latest versions of all these dependencies. This
  tarball, located at
  http://tahoe-lafs.org/source/tahoe/deps/tahoe-deps.tar.gz, can be
  unpacked in the tahoe source tree (or in its parent directory), and
  the build process should satisfy its downloading needs from it
  instead of reaching out to PyPI.  This can be useful if you want to
  build Tahoe from a darcs checkout while on that airplane or desert
  island.

- Because of the previous two changes ("sumo" tarballs and the
  "tahoe-deps" bundle), most of the files have been removed from
  misc/dependencies/ . This brings the regular Tahoe tarball down to
  2MB (compressed), and the darcs checkout (without history) to about
  7.6MB. A full darcs checkout will still be fairly large (because of
  the historical patches which included the dependent libraries), but
  a 'lazy' one should now be small.

- The default "make" target is now an alias for "setup.py build",
  which itself is an alias for "setup.py develop --prefix support",
  with some extra work before and after (see setup.cfg). Most of the
  complicated platform-dependent code in the Makefile was rewritten in
  Python and moved into setup.py, simplifying things considerably.

- Likewise, the "make test" target now delegates most of its work to
  "setup.py test", which takes care of getting PYTHONPATH configured
  to access the tahoe code (and dependencies) that gets put in
  support/lib/ by the build_tahoe step. This should allow unit tests
  to be run even when trial (which is part of Twisted) wasn't already
  installed (in this case, trial gets installed to support/bin because
  Twisted is a dependency of Tahoe).

- Tahoe is now compatible with the recently-released Python 2.6 ,
  although it is recommended to use Tahoe on Python 2.5, on which it
  has received more thorough testing and deployment.

- Tahoe is now compatible with simplejson-2.0.x . The previous release
  assumed that simplejson.loads always returned unicode strings, which
  is no longer the case in 2.0.x .

Grid Management Tools
'''''''''''''''''''''

- Several tools have been added or updated in the misc/ directory,
  mostly munin plugins that can be used to monitor a storage grid.

 - The misc/spacetime/ directory contains a "disk watcher" daemon
   (startable with 'tahoe start'), which can be configured with a set
   of HTTP URLs (pointing at the wapi '/statistics' page of a bunch of
   storage servers), and will periodically fetch
   disk-used/disk-available information from all the servers. It keeps
   this information in an Axiom database (a sqlite-based library
   available from divmod.org). The daemon computes time-averaged rates
   of disk usage, as well as a prediction of how much time is left
   before the grid is completely full.

 - The misc/munin/ directory contains a new set of munin plugins
   (tahoe_diskleft, tahoe_diskusage, tahoe_doomsday) which talk to the
   disk-watcher and provide graphs of its calculations.

 - To support the disk-watcher, the Tahoe statistics component
   (visible through the wapi at the /statistics/ URL) now includes
   disk-used and disk-available information. Both are derived through
   an equivalent of the unix 'df' command (i.e. they ask the kernel
   for the number of free blocks on the partition that encloses the
   BASEDIR/storage directory). In the future, the disk-available
   number will be further influenced by the local storage policy: if
   that policy says that the server should refuse new shares when less
   than 5GB is left on the partition, then "disk-available" will
   report zero even though the kernel sees 5GB remaining.

 - The 'tahoe_overhead' munin plugin interacts with an
   allmydata.com-specific server which reports the total of the
   'deep-size' reports for all active user accounts, compares this
   with the disk-watcher data, to report on overhead percentages. This
   provides information on how much space could be recovered once
   Tahoe implements some form of garbage collection.

Configuration Changes: single INI-format tahoe.cfg file
'''''''''''''''''''''''''''''''''''''''''''''''''''''''

- The Tahoe node is now configured with a single INI-format file,
  named "tahoe.cfg", in the node's base directory. Most of the
  previous multiple-separate-files are still read for backwards
  compatibility (the embedded SSH debug server and the
  advertised_ip_addresses files are the exceptions), but new
  directives will only be added to tahoe.cfg . The "tahoe
  create-client" command will create a tahoe.cfg for you, with sample
  values commented out. (ticket `#518`_)

- tahoe.cfg now has controls for the foolscap "keepalive" and
  "disconnect" timeouts (`#521`_).

- tahoe.cfg now has controls for the encoding parameters:
  "shares.needed" and "shares.total" in the "[client]" section. The
  default parameters are still 3-of-10.

- The inefficient storage 'sizelimit' control (which established an
  upper bound on the amount of space that a storage server is allowed
  to consume) has been replaced by a lightweight 'reserved_space'
  control (which establishes a lower bound on the amount of remaining
  space). The storage server will reject all writes that would cause
  the remaining disk space (as measured by a '/bin/df' equivalent) to
  drop below this value. The "[storage]reserved_space=" tahoe.cfg
  parameter controls this setting. (note that this only affects
  immutable shares: it is an outstanding bug that reserved_space does
  not prevent the allocation of new mutable shares, nor does it
  prevent the growth of existing mutable shares).

Other Changes
'''''''''''''

- Clients now declare which versions of the protocols they
  support. This is part of a new backwards-compatibility system:
  http://tahoe-lafs.org/trac/tahoe/wiki/Versioning .

- The version strings for human inspection (as displayed on the
  Welcome web page, and included in logs) now includes a platform
  identifer (frequently including a linux distribution name, processor
  architecture, etc).

- Several bugs have been fixed, including one that would cause an
  exception (in the logs) if a wapi download operation was cancelled
  (by closing the TCP connection, or pushing the "stop" button in a
  web browser).

- Tahoe now uses Foolscap "Incidents", writing an "incident report"
  file to logs/incidents/ each time something weird occurs. These
  reports are available to an "incident gatherer" through the flogtool
  command. For more details, please see the Foolscap logging
  documentation. An incident-classifying plugin function is provided
  in misc/incident-gatherer/classify_tahoe.py .

- If clients detect corruption in shares, they now automatically
  report it to the server holding that share, if it is new enough to
  accept the report.  These reports are written to files in
  BASEDIR/storage/corruption-advisories .

- The 'nickname' setting is now defined to be a UTF-8 -encoded string,
  allowing non-ascii nicknames.

- The 'tahoe start' command will now accept a --syslog argument and
  pass it through to twistd, making it easier to launch non-Tahoe
  nodes (like the cpu-watcher) and have them log to syslogd instead of
  a local file. This is useful when running a Tahoe node out of a USB
  flash drive.

- The Mac GUI in src/allmydata/gui/ has been improved.

.. _#512: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/512
.. _#518: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/518
.. _#521: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/521
.. _#531: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/531

Release 1.2.0 (2008-07-21)
--------------------------

Security
''''''''

- This release makes the immutable-file "ciphertext hash tree"
  mandatory.  Previous releases allowed the uploader to decide whether
  their file would have an integrity check on the ciphertext or not. A
  malicious uploader could use this to create a readcap that would
  download as one file or a different one, depending upon which shares
  the client fetched first, with no errors raised. There are other
  integrity checks on the shares themselves, preventing a storage
  server or other party from violating the integrity properties of the
  read-cap: this failure was only exploitable by the uploader who
  gives you a carefully constructed read-cap. If you download the file
  with Tahoe 1.2.0 or later, you will not be vulnerable to this
  problem. `#491`_

  This change does not introduce a compatibility issue, because all
  existing versions of Tahoe will emit the ciphertext hash tree in
  their shares.

Dependencies
''''''''''''

- Tahoe now requires Foolscap-0.2.9 . It also requires pycryptopp 0.5
  or newer, since earlier versions had a bug that interacted with
  specific compiler versions that could sometimes result in incorrect
  encryption behavior. Both packages are included in the Tahoe source
  tarball in misc/dependencies/ , and should be built automatically
  when necessary.

Web API
'''''''

- Web API directory pages should now contain properly-slash-terminated
  links to other directories. They have also stopped using absolute
  links in forms and pages (which interfered with the use of a
  front-end load-balancing proxy).

- The behavior of the "Check This File" button changed, in conjunction
  with larger internal changes to file checking/verification. The
  button triggers an immediate check as before, but the outcome is
  shown on its own page, and does not get stored anywhere. As a
  result, the web directory page no longer shows historical checker
  results.

- A new "Deep-Check" button has been added, which allows a user to
  initiate a recursive check of the given directory and all files and
  directories reachable from it. This can cause quite a bit of work,
  and has no intermediate progress information or feedback about the
  process. In addition, the results of the deep-check are extremely
  limited. A later release will improve this behavior.

- The web server's behavior with respect to non-ASCII (unicode)
  filenames in the "GET save=true" operation has been improved. To
  achieve maximum compatibility with variously buggy web browsers, the
  server does not try to figure out the character set of the inbound
  filename. It just echoes the same bytes back to the browser in the
  Content-Disposition header. This seems to make both IE7 and Firefox
  work correctly.

Checker/Verifier/Repairer
'''''''''''''''''''''''''

- Tahoe is slowly acquiring convenient tools to check up on file
  health, examine existing shares for errors, and repair files that
  are not fully healthy. This release adds a mutable
  checker/verifier/repairer, although testing is very limited, and
  there are no web interfaces to trigger repair yet. The "Check"
  button next to each file or directory on the wapi page will perform
  a file check, and the "deep check" button on each directory will
  recursively check all files and directories reachable from there
  (which may take a very long time).

  Future releases will improve access to this functionality.

Operations/Packaging
''''''''''''''''''''

- A "check-grid" script has been added, along with a Makefile
  target. This is intended (with the help of a pre-configured node
  directory) to check upon the health of a Tahoe grid, uploading and
  downloading a few files. This can be used as a monitoring tool for a
  deployed grid, to be run periodically and to signal an error if it
  ever fails. It also helps with compatibility testing, to verify that
  the latest Tahoe code is still able to handle files created by an
  older version.

- The munin plugins from misc/munin/ are now copied into any generated
  debian packages, and are made executable (and uncompressed) so they
  can be symlinked directly from /etc/munin/plugins/ .

- Ubuntu "Hardy" was added as a supported debian platform, with a
  Makefile target to produce hardy .deb packages. Some notes have been
  added to `debian.rst`_ about building Tahoe on a debian/ubuntu
  system.

- Storage servers now measure operation rates and
  latency-per-operation, and provides results through the /statistics
  web page as well as the stats gatherer. Munin plugins have been
  added to match.

Other
'''''

- Tahoe nodes now use Foolscap "incident logging" to record unusual
  events to their NODEDIR/logs/incidents/ directory. These incident
  files can be examined by Foolscap logging tools, or delivered to an
  external log-gatherer for further analysis. Note that Tahoe now
  requires Foolscap-0.2.9, since 0.2.8 had a bug that complained about
  "OSError: File exists" when trying to create the incidents/
  directory for a second time.

- If no servers are available when retrieving a mutable file (like a
  directory), the node now reports an error instead of hanging
  forever. Earlier releases would not only hang (causing the wapi
  directory listing to get stuck half-way through), but the internal
  dirnode serialization would cause all subsequent attempts to
  retrieve or modify the same directory to hang as well. `#463`_

- A minor internal exception (reported in logs/twistd.log, in the
  "stopProducing" method) was fixed, which complained about
  "self._paused_at not defined" whenever a file download was stopped
  from the web browser end.

.. _#463: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/463
.. _#491: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/491
.. _debian.rst: docs/debian.rst

Release 1.1.0 (2008-06-11)
--------------------------

CLI: new "alias" model
''''''''''''''''''''''

- The new CLI code uses an scp/rsync -like interface, in which
  directories in the Tahoe storage grid are referenced by a
  colon-suffixed alias. The new commands look like:

 - tahoe cp local.txt tahoe:virtual.txt
 - tahoe ls work:subdir

- More functionality is available through the CLI: creating unlinked
  files and directories, recursive copy in or out of the storage grid,
  hardlinks, and retrieving the raw read- or write- caps through the
  'ls' command. Please read `CLI.rst`_ for complete details.

wapi: new pages, new commands
'''''''''''''''''''''''''''''

- Several new pages were added to the web API:

 - /helper_status : to describe what a Helper is doing
 - /statistics : reports node uptime, CPU usage, other stats
 - /file : for easy file-download URLs, see `#221`_
 - /cap == /uri : future compatibility

- The localdir=/localfile= and t=download operations were
  removed. These required special configuration to enable anyways, but
  this feature was a security problem, and was mostly obviated by the
  new "cp -r" command.

- Several new options to the GET command were added:

 -  t=deep-size : add up the size of all immutable files reachable from the directory
 -  t=deep-stats : return a JSON-encoded description of number of files, size distribution, total size, etc

- POST is now preferred over PUT for most operations which cause
  side-effects.

- Most wapi calls now accept overwrite=, and default to overwrite=true

- "POST /uri/DIRCAP/parent/child?t=mkdir" is now the preferred API to
  create multiple directories at once, rather than ...?t=mkdir-p .

- PUT to a mutable file ("PUT /uri/MUTABLEFILECAP", "PUT
  /uri/DIRCAP/child") will modify the file in-place.

- more munin graphs in misc/munin/

 - tahoe-introstats
 - tahoe-rootdir-space
 - tahoe_estimate_files
 - mutable files published/retrieved
 - tahoe_cpu_watcher
 - tahoe_spacetime

New Dependencies
''''''''''''''''
-  zfec 1.1.0
-  foolscap 0.2.8
-  pycryptopp 0.5
-  setuptools (now required at runtime)

New Mutable-File Code
'''''''''''''''''''''

- The mutable-file handling code (mostly used for directories) has
  been completely rewritten. The new scheme has a better API (with a
  modify() method) and is less likely to lose data when several
  uncoordinated writers change a file at the same time.

- In addition, a single Tahoe process will coordinate its own
  writes. If you make two concurrent directory-modifying wapi calls to
  a single tahoe node, it will internally make one of them wait for
  the other to complete. This prevents auto-collision (`#391`_).

- The new mutable-file code also detects errors during publish
  better. Earlier releases might believe that a mutable file was
  published when in fact it failed.

other features
''''''''''''''

- The node now monitors its own CPU usage, as a percentage, measured
  every 60 seconds. 1/5/15 minute moving averages are available on the
  /statistics web page and via the stats-gathering interface.

- Clients now accelerate reconnection to all servers after being
  offline (`#374`_). When a client is offline for a long time, it
  scales back reconnection attempts to approximately once per hour, so
  it may take a while to make the first attempt, but once any attempt
  succeeds, the other server connections will be retried immediately.

- A new "offloaded KeyGenerator" facility can be configured, to move
  RSA key generation out from, say, a wapi node, into a separate
  process. RSA keys can take several seconds to create, and so a wapi
  node which is being used for directory creation will be unavailable
  for anything else during this time. The Key Generator process will
  pre-compute a small pool of keys, to speed things up further. This
  also takes better advantage of multi-core CPUs, or SMP hosts.

- The node will only use a potentially-slow "du -s" command at startup
  (to measure how much space has been used) if the "sizelimit"
  parameter has been configured (to limit how much space is
  used). Large storage servers should turn off sizelimit until a later
  release improves the space-management code, since "du -s" on a
  terabyte filesystem can take hours.

- The Introducer now allows new announcements to replace old ones, to
  avoid buildups of obsolete announcements.

- Immutable files are limited to about 12GiB (when using the default
  3-of-10 encoding), because larger files would be corrupted by the
  four-byte share-size field on the storage servers (`#439`_). A later
  release will remove this limit. Earlier releases would allow >12GiB
  uploads, but the resulting file would be unretrievable.

- The docs/ directory has been rearranged, with old docs put in
  docs/historical/ and not-yet-implemented ones in docs/proposed/ .

- The Mac OS-X FUSE plugin has a significant bug fix: earlier versions
  would corrupt writes that used seek() instead of writing the file in
  linear order.  The rsync tool is known to perform writes in this
  order. This has been fixed.

.. _#221: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/221
.. _#374: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/374
.. _#391: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/391
.. _#439: http://tahoe-lafs.org/trac/tahoe-lafs/ticket/439
.. _CLI.rst: docs/CLI.rst
