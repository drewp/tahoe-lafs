# -*- test-case-name: allmydata.test.test_hashtree -*-

"""
Read and write chunks from files.

Version 1.0.0.

A file is divided into blocks, each of which has size L{BLOCK_SIZE}
(except for the last block, which may be smaller).  Blocks are encoded
into chunks.  One publishes the hash of the entire file.  Clients
who want to download the file first obtain the hash, then the clients
can receive chunks in any order.  Cryptographic hashing is used to
verify each received chunk before writing to disk.  Thus it is
impossible to download corrupt data if one has the correct file hash.

One obtains the hash of a complete file via
L{CompleteChunkFile.file_hash}.  One can read chunks from a complete
file by the sequence operations of C{len()} and subscripting on a
L{CompleteChunkFile} object.  One can open an empty or partially
downloaded file with L{PartialChunkFile}, and read and write chunks
to this file.  A chunk will fail to write if its contents and index
are not consistent with the overall file hash passed to
L{PartialChunkFile} when the partial chunk file was first created.

The chunks have an overhead of less than 4% for files of size
less than C{10**20} bytes.

Benchmarks:

 - On a 3 GHz Pentium 3, it took 3.4 minutes to first make a
   L{CompleteChunkFile} object for a 4 GB file.  Up to 10 MB of
   memory was used as the constructor ran.  A metafile filename
   was passed to the constructor, and so the hash information was
   written to the metafile.  The object used a negligible amount
   of memory after the constructor was finished.
 - Creation of L{CompleteChunkFile} objects in future runs of the
   program took negligible time, since the hash information was
   already stored in the metafile.

@var BLOCK_SIZE:     Size of a block.  See L{BlockFile}.
@var MAX_CHUNK_SIZE: Upper bound on the size of a chunk.
                     See L{CompleteChunkFile}.

free (adj.): unencumbered; not under the control of others
Written by Connelly Barnes in 2005 and released into the
public domain  with no warranty of any kind, either expressed
or implied.  It probably won't make your computer catch on fire,
or eat  your children, but it might.  Use at your own risk.
"""

from allmydata.util import idlib
from allmydata.util.hashutil import tagged_hash, tagged_pair_hash

__version__ = '1.0.0-allmydata'

BLOCK_SIZE     = 65536
MAX_CHUNK_SIZE = BLOCK_SIZE + 4096

def roundup_pow2(x):
  """
  Round integer C{x} up to the nearest power of 2.
  """
  ans = 1
  while ans < x:
    ans *= 2
  return ans


class CompleteBinaryTreeMixin:
  """
  Adds convenience methods to a complete binary tree.

  Assumes the total number of elements in the binary tree may be
  accessed via C{__len__}, and that each element can be retrieved
  using list subscripting.

  Tree is indexed like so::


                      0
                 /        \
              1               2
           /    \          /    \
         3       4       5       6
        / \     / \     / \     / \
       7   8   9   10  11  12  13  14

  """
  def parent(self, i):
    """
    Index of the parent of C{i}.
    """
    if i < 1 or (hasattr(self, '__len__') and i >= len(self)):
      raise IndexError('index out of range: ' + repr(i))
    return (i - 1) // 2

  def lchild(self, i):
    """
    Index of the left child of C{i}.
    """
    ans = 2 * i + 1
    if i < 0 or (hasattr(self, '__len__') and ans >= len(self)):
      raise IndexError('index out of range: ' + repr(i))
    return ans

  def rchild(self, i):
    """
    Index of right child of C{i}.
    """
    ans = 2 * i + 2
    if i < 0 or (hasattr(self, '__len__') and ans >= len(self)):
      raise IndexError('index out of range: ' + repr(i))
    return ans

  def sibling(self, i):
    """
    Index of sibling of C{i}.
    """
    parent = self.parent(i)
    if self.lchild(parent) == i:
      return self.rchild(parent)
    else:
      return self.lchild(parent)

  def needed_for(self, i):
    """
    Return a list of node indices that are necessary for the hash chain.
    """
    if i < 0 or i >= len(self):
      raise IndexError('index out of range: ' + repr(i))
    needed = []
    here = i
    while here != 0:
      needed.append(self.sibling(here))
      here = self.parent(here)
    return needed

  def depth_first(self, i=0):
    yield i, 0
    try:
      for child,childdepth in self.depth_first(self.lchild(i)):
        yield child, childdepth+1
    except IndexError:
      pass
    try:
      for child,childdepth in self.depth_first(self.rchild(i)):
        yield child, childdepth+1
    except IndexError:
      pass

  def dump(self):
    lines = []
    for i,depth in self.depth_first():
      lines.append("%s%3d: %s" % ("  "*depth, i, idlib.b2a_or_none(self[i])))
    return "\n".join(lines) + "\n"

def empty_leaf_hash(i):
  return tagged_hash('Merkle tree empty leaf', "%d" % i)
def pair_hash(a, b):
  return tagged_pair_hash('Merkle tree internal node', a, b)

class HashTree(CompleteBinaryTreeMixin, list):
  """
  Compute Merkle hashes at any node in a complete binary tree.

  Tree is indexed like so::


                      0
                 /        \
              1               2
           /    \          /    \
         3       4       5       6
        / \     / \     / \     / \
       7   8   9   10  11  12  13  14  <- List passed to constructor.

  """
  def __init__(self, L):
    """
    Create complete binary tree from list of hash strings.

    The list is augmented by hashes so its length is a power of 2, and
    then this is used as the bottom row of the hash tree.

    The augmenting is done so that if the augmented element is at
    index C{i}, then its value is C{hash(tagged_hash('Merkle tree empty leaf', '%d'%i))}.
    """
    # Augment the list.
    start = len(L)
    end   = roundup_pow2(len(L))
    L     = L + [None] * (end - start)
    for i in range(start, end):
      L[i] = empty_leaf_hash(i)
    # Form each row of the tree.
    rows = [L]
    while len(rows[-1]) != 1:
      last = rows[-1]
      rows += [[pair_hash(last[2*i], last[2*i+1])
                for i in xrange(len(last)//2)]]
    # Flatten the list of rows into a single list.
    rows.reverse()
    self[:] = sum(rows, [])


class NotEnoughHashesError(Exception):
  pass

class BadHashError(Exception):
  pass

class IncompleteHashTree(CompleteBinaryTreeMixin, list):
  """I am a hash tree which may or may not be complete. I can be used to
  validate inbound data from some untrustworthy provider who has a subset of
  leaves and a sufficient subset of internal nodes.

  Initially I am completely unpopulated. Over time, I will become filled with
  hashes, just enough to validate particular leaf nodes.

  If you desire to validate leaf number N, first find out which hashes I need
  by calling needed_hashes(N). This will return a list of node numbers (which
  will nominally be the sibling chain between the given leaf and the root,
  but if I already have some of those nodes, needed_hashes(N) will only
  return a subset). Obtain these hashes from the data provider, then tell me
  about them with set_hash(i, HASH). Once I have enough hashes, you can tell
  me the hash of the leaf with set_leaf_hash(N, HASH), and I will either
  return None or raise BadHashError.

  The first hash to be set will probably be 0 (the root hash), since this is
  the one that will come from someone more trustworthy than the data
  provider.

  """

  def __init__(self, num_leaves):
    L = [None] * num_leaves
    start = len(L)
    end   = roundup_pow2(len(L))
    self.first_leaf_num = end - 1
    L     = L + [None] * (end - start)
    rows = [L]
    while len(rows[-1]) != 1:
      last = rows[-1]
      rows += [[None for i in xrange(len(last)//2)]]
    # Flatten the list of rows into a single list.
    rows.reverse()
    self[:] = sum(rows, [])

  def needed_hashes(self, hashes=[], leaves=[]):
    hashnums = set(list(hashes))
    for leafnum in leaves:
      hashnums.add(self.first_leaf_num + leafnum)
    maybe_needed = set()
    for hashnum in hashnums:
      maybe_needed.update(self.needed_for(hashnum))
    maybe_needed.add(0) # need the root too
    return set([i for i in maybe_needed if self[i] is None])


  def set_hashes(self, hashes={}, leaves={}, must_validate=False):
    """Add a bunch of hashes to the tree.

    I will validate these to the best of my ability. If I already have a copy
    of any of the new hashes, the new values must equal the existing ones, or
    I will raise BadHashError. If adding a hash allows me to compute a parent
    hash, those parent hashes must match or I will raise BadHashError. If I
    raise BadHashError, I will forget about all the hashes that you tried to
    add, leaving my state exactly the same as before I was called. If I
    return successfully, I will remember all those hashes.

    If every hash that was added was validated, I will return True. If some
    could not be validated because I did not have enough parent hashes, I
    will return False. As a result, if I am called with both a leaf hash and
    the root hash was already set, I will return True if and only if the leaf
    hash could be validated against the root.

    If must_validate is True, I will raise NotEnoughHashesError instead of
    returning False. If I raise NotEnoughHashesError, I will forget about all
    the hashes that you tried to add. TODO: really?

    'leaves' is a dictionary uses 'leaf index' values, which range from 0
    (the left-most leaf) to num_leaves-1 (the right-most leaf), and form the
    base of the tree. 'hashes' uses 'hash_index' values, which range from 0
    (the root of the tree) to 2*num_leaves-2 (the right-most leaf). leaf[i]
    is the same as hash[num_leaves-1+i].

    The best way to use me is to obtain the root hash from some 'good'
    channel, then call set_hash(0, root). Then use the 'bad' channel to
    obtain data block 0 and the corresponding hash chain (a dict with the
    same hashes that needed_hashes(0) tells you, e.g. {0:h0, 2:h2, 4:h4,
    8:h8} when len(L)=8). Hash the data block to create leaf0. Then call::

     good = iht.set_hashes(hashes=hashchain, leaves={0: leaf0})

    If 'good' is True, the data block was valid. If 'good' is False, the
    hashchain did not have the right blocks and we don't know whether the
    data block was good or bad. If set_hashes() raises an exception, either
    the data was corrupted or one of the received hashes was corrupted.
    """

    assert isinstance(hashes, dict)
    assert isinstance(leaves, dict)
    new_hashes = hashes.copy()
    for leafnum,leafhash in leaves.iteritems():
      hashnum = self.first_leaf_num + leafnum
      if hashnum in new_hashes:
        assert new_hashes[hashnum] == leafhash
      new_hashes[hashnum] = leafhash

    added = set() # we'll remove these if the check fails

    try:
      # first we provisionally add all hashes to the tree, comparing any
      # duplicates
      for i in new_hashes:
        if self[i]:
          if self[i] != new_hashes[i]:
            raise BadHashError("new hash does not match existing hash at [%d]"
                               % i)
        else:
          self[i] = new_hashes[i]
          added.add(i)

      # then we start from the bottom and compute new parent hashes upwards,
      # comparing any that already exist. When this phase ends, all nodes
      # that have a sibling will also have a parent.

      hashes_to_check = list(new_hashes.keys())
      # leaf-most first means reverse sorted order
      while hashes_to_check:
        hashes_to_check.sort()
        i = hashes_to_check.pop(-1)
        if i == 0:
          # The root has no sibling. How lonely.
          continue
        if self[self.sibling(i)] is None:
          # without a sibling, we can't compute a parent
          continue
        parentnum = self.parent(i)
        # make sure we know right from left
        leftnum, rightnum = sorted([i, self.sibling(i)])
        new_parent_hash = pair_hash(self[leftnum], self[rightnum])
        if self[parentnum]:
          if self[parentnum] != new_parent_hash:
            raise BadHashError("h([%d]+[%d]) != h[%d]" % (leftnum, rightnum,
                                                          parentnum))
        else:
          self[parentnum] = new_parent_hash
          added.add(parentnum)
          hashes_to_check.insert(0, parentnum)

      # then we walk downwards from the top (root), and anything that is
      # reachable is validated. If any of the hashes that we've added are
      # unreachable, then they are unvalidated.

      reachable = set()
      if self[0]:
        reachable.add(0)
      # TODO: this could be done more efficiently, by starting from each
      # element of new_hashes and walking upwards instead, remembering a set
      # of validated nodes so that the searches for later new_hashes goes
      # faster. This approach is O(n), whereas O(ln(n)) should be feasible.
      for i in range(1, len(self)):
        if self[i] and self.parent(i) in reachable:
          reachable.add(i)

      # were we unable to validate any of the new hashes?
      unvalidated = set(new_hashes.keys()) - reachable
      if unvalidated:
        if must_validate:
          those = ",".join([str(i) for i in sorted(unvalidated)])
          raise NotEnoughHashesError("unable to validate hashes %s" % those)

    except (BadHashError, NotEnoughHashesError):
      for i in added:
        self[i] = None
      raise

    # if there were hashes that could not be validated, we return False
    return not unvalidated

