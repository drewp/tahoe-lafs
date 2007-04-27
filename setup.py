#! /usr/bin/env python

# Allmydata Tahoe -- secure, distributed storage mesh
# 
# Copyright (C) 2007 Allmydata, Inc.
# 
# This file is part of tahoe.
# 
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation; either version 2 of the License, or (at your option)
# any later version, with the added permission that, if you become obligated
# to release a derived work under this licence (as per section 2.b), you may
# delay the fulfillment of this obligation for up to 12 months.  See the file
# COPYING for details.
#
# If you would like to inquire about a commercial relationship with Allmydata,
# Inc., please contact partnerships@allmydata.com and visit
# http://allmydata.com/.
# 
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.

from distutils.core import Extension, setup

trove_classifiers=[
    "Development Status :: 3 - Alpha", 
    "Environment :: Console",
    "Environment :: Web Environment",
    "License :: OSI Approved :: GNU General Public License (GPL)", 
    "Intended Audience :: Developers", 
    "Intended Audience :: End Users/Desktop",
    "Intended Audience :: System Administrators",
    "Operating System :: Microsoft",
    "Operating System :: Microsoft :: Windows",
    "Operating System :: Unix",
    "Operating System :: POSIX :: Linux",
    "Operating System :: POSIX",
    "Operating System :: MacOS :: MacOS X",
    "Operating System :: Microsoft :: Windows :: Windows NT/2000",
    "Operating System :: OS Independent", 
    "Natural Language :: English", 
    "Programming Language :: C", 
    "Programming Language :: Python", 
    "Topic :: Utilities",
    "Topic :: System :: Systems Administration",
    "Topic :: System :: Filesystems",
    "Topic :: System :: Distributed Computing",
    "Topic :: Software Development :: Libraries",
    "Topic :: Communications :: Usenet News",
    "Topic :: System :: Archiving :: Backup", 
    "Topic :: System :: Archiving :: Mirroring", 
    "Topic :: System :: Archiving", 
    ]

setup(name='allmydata-tahoe',
      version='0.1.1',
      description='secure, distributed storage mesh',
      long_description="""Welcome to the AllMyData "tahoe" project. This project implements a
secure, distributed, fault-tolerant storage mesh.

The basic idea is that the data in this storage mesh is spread over all
participating nodes, using an algorithm that can recover the data even if a
majority of the nodes are no longer available.""",
      author='Allmydata, Inc.',
      author_email='tahoe-dev@allmydata.org',
      url='http://allmydata.org/',
      license='GNU GPL',
      packages=["allmydata", "allmydata.test", "allmydata.util",
                "allmydata.filetree", "allmydata.scripts",],
      package_dir={ "allmydata": "src/allmydata",},
      scripts = ["bin/allmydata-tahoe"],
      package_data={ 'allmydata': ['web/*.xhtml'] },
      classifiers=trove_classifiers,
      test_suite="allmydata.test",
      )
