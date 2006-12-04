import os

from foolscap import Referenceable
from twisted.application import service
from twisted.python.failure import Failure
from allmydata.util import idlib
from zope.interface import implements
from allmydata.interfaces import RIBucketWriter, RIBucketReader

from allmydata.util.assertutil import precondition, _assert

class NoSuchBucketError(Failure):
    pass

class BucketStore(service.MultiService, Referenceable):
    def __init__(self, store_dir):
        precondition(os.path.isdir(store_dir))
        service.MultiService.__init__(self)
        self._store_dir = store_dir

        self._leases = set() # should do weakref dances.

    def _get_bucket_dir(self, verifierid):
        avid = idlib.b2a(verifierid)
        return os.path.join(self._store_dir, avid)

    def has_bucket(self, verifierid):
        return os.path.exists(self._get_bucket_dir(verifierid))

    def allocate_bucket(self, verifierid, bucket_num, size,
                        leaser_credentials, canary):
        bucket_dir = self._get_bucket_dir(verifierid)
        precondition(not os.path.exists(bucket_dir))
        precondition(isinstance(bucket_num, int))
        bucket = WriteBucket(bucket_dir, verifierid, bucket_num, size)
        bucket.set_leaser(leaser_credentials)
        lease = Lease(verifierid, leaser_credentials, bucket, canary)
        self._leases.add(lease)
        return lease

    def get_buckets(self, verifierid):
        # for now, only returns those created by this process, in this run
        bucket_dir = self._get_bucket_dir(verifierid)
        if os.path.exists(bucket_dir):
            b = ReadBucket(bucket_dir, verifierid)
            return [(b.get_bucket_num(), b)]
        else:
            return []

class Lease(Referenceable):
    implements(RIBucketWriter)

    def __init__(self, verifierid, leaser, bucket, canary):
        self._leaser = leaser
        self._verifierid = verifierid
        self._bucket = bucket
        canary.notifyOnDisconnect(self._lost_canary)

    def get_bucket(self):
        return self._bucket

    def remote_write(self, data):
        self._bucket.write(data)

    def remote_close(self):
        self._bucket.close()

    def _lost_canary(self):
        pass

class Bucket:
    def __init__(self, bucket_dir, verifierid):
        self._bucket_dir = bucket_dir
        self._verifierid = verifierid

    def _write_attr(self, name, val):
        f = file(os.path.join(self._bucket_dir, name), 'wb')
        f.write(val)
        f.close()

    def _read_attr(self, name):
        f = file(os.path.join(self._bucket_dir, name), 'rb')
        data = f.read()
        f.close()
        return data

    def is_complete(self):
        return os.path.exists(os.path.join(self._bucket_dir, 'closed'))

class WriteBucket(Bucket):
    def __init__(self, bucket_dir, verifierid, bucket_num, size):
        Bucket.__init__(self, bucket_dir, verifierid)
        precondition(not os.path.exists(bucket_dir))
        os.mkdir(bucket_dir)

        self._size = size
        self._data = file(os.path.join(self._bucket_dir, 'data'), 'wb')
        self._bytes_written = 0

        self._write_attr('bucket_num', str(bucket_num))

    def set_leaser(self, leaser):
        self._write_attr('leases', leaser)

    def write(self, data):
        precondition(len(data) + self._bytes_written <= self._size)
        self._data.write(data)
        self._data.flush()
        self._bytes_written += len(data)

    def close(self):
        precondition(self._bytes_written == self._size)
        self._data.close()
        self._write_attr('closed', '')

    def is_complete(self):
        complete = Bucket.is_complete(self)
        if complete:
            _assert(os.path.getsize(os.path.join(self._bucket_dir, 'data')) == self._size)
        return complete

class ReadBucket(Bucket, Referenceable):
    implements(RIBucketReader)

    def __init__(self, bucket_dir, verifierid):
        Bucket.__init__(self, bucket_dir, verifierid)
        precondition(self.is_complete()) # implicitly asserts bucket_dir exists

    def get_bucket_num(self):
        return int(self._read_attr('bucket_num'))
    remote_get_bucket_num = get_bucket_num

    def read(self):
        return self._read_attr('data')
    remote_read = read
