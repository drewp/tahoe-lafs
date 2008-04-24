#! /usr/bin/python

import sys, os.path

if len(sys.argv) > 1 and sys.argv[1] == "config":
    print """\
graph_title Tahoe File Estimate
graph_vlabel files
graph_category tahoe
graph_info This graph shows the estimated number of files and directories present in the grid
files.label files
files.draw LINE2"""
    sys.exit(0)

# Edit this to point at some subset of storage directories.
node_dirs = [os.path.expanduser("~amduser/prodnet/storage1"),
             os.path.expanduser("~amduser/prodnet/storage2"),
             os.path.expanduser("~amduser/prodnet/storage3"),
             os.path.expanduser("~amduser/prodnet/storage4"),
             ]

sections = ["aa", "ab", "ac", "ad", "ae", "af", "ag", "ah", "ai", "aj"]
# and edit this to reflect your default encoding's "total_shares" value, and
# the total number of servers.
N = 10
num_servers = 20

index_strings = set()
for base in node_dirs:
    for section in sections:
        sampledir = os.path.join(base, "storage", "shares", section)
        indices = os.listdir(sampledir)
        index_strings.update(indices)
unique_strings = len(index_strings)

# the chance that any given file appears on any given server
chance = 1.0 * N / num_servers

# the chance that the file does *not* appear on the servers that we're
# examining
no_chance = (1-chance) ** len(node_dirs)

# if a file has a 25% chance of not appearing in our sample, then we need to
# raise our estimate by (1.25/1)
correction = 1+no_chance
#print "correction", correction

files = unique_strings * (32*32/len(sections)) * correction
print "files.value %d" % int(files)
