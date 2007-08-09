from __future__ import absolute_import

import sha, md5
from os import makedirs
import cPickle as pickle

from django.db import models

from .media import Media

class ContentStore(object):
    """ Base class for a generic content store """

    __slots__ = ( 'key', '_sha1', 'visibility', 'offset', 'size',
                  '_chunk', '_chunkgen' )

    def metakey(self):
        return '%s__meta' % self.key
    
    def __init__(self, key):
        if key.endswith('__meta'):
            raise KeyError('bad key name %s' % key)

        self._sha1 = None

        self.key = key
        self.offset = 0

        self._chunkgen = None
        self._chunk = None

    def sha1(self):
        if self._sha1 is None:
            self._sha1 = self.get_sha1()
        return self._sha1

    def store(self, data, sha1=None, vis='private'):
        assert vis in ('private', 'public')

        if sha1 is None:
            sha1 = sha.new(data)
            sha1 = sha1.digest().encode('hex')
            
        self._sha1 = sha1
        self.visibility = vis

        self._store(key, data)
        if True:
            self.verify()

        self.seek(0)

    def verify(self):
        sha1 = sha.new()

        for chunk in self.chunks():
            sha1.update(chunk)

        return sha1.digest().encode('hex') == self.sha1()

    def tell(self):
        return self.offset    

    def seek(self, off, whence = 0):
        if whence == 0:
            pass
        elif whence == 1:
            off = self.off + off
        elif whence == 2:
            off = self.size() + off

        assert off >= 0 and off < self.size

        # slow but generic
        self.offset = off
        chunk = None
        chunkbase = 0
        self._chunkgen = self.chunks()
        for c in self._chunkgen:
            if chunkbase <= off and chunkbase + len(c) >= off:
                chunk = c
                break
            chunkbase += len(c)

        assert chunk is not None

        self._chunk = chunk

        return off
    
    def read(self, size=None):
        if self._chunkgen is None:
            self._chunkgen = self.chunks()
            
        if self._chunk is None:
            try:
                self._chunk = self._chunkgen.next()
            except StopIteration:
                return ''                # EOF

        if size is None or size < 0 or size > len(self._chunk):
            size = len(self._chunk)

        ret = self._chunk[:size]
        self.offset += size
        self._chunk = self._chunk[size:]

        if len(self._chunk) == 0:
            self._chunk = None

        return ret

class DBContentStore(ContentStore):
    def _store(self, data):
        Media.store(data, self.key, self._sha1)

    def _get(self):
        return Media.get(self.key)

    def size(self):
        return self.get().datasize

    def get_sha1(self):
        return Media.get(self.key).sha1hash

    def chunks(self):
        return Media.get(self.key).chunks()

class FileContentStore(ContentStore):
    class meta(object):
        def __init__(self, sha1):
            self.sha1 = sha1

    def dirname(self):
        return 'data/'

    def filename(self):
        return self.dirname() + self.key

    def metaname(self):
        return self.dirname() + self.metakey()

    def _store(self, data):
        __slots__ = [ 'file' ]
        
        makedirs(self.dirname())
        
        f = open(self.filename(), 'w')
        f.write(data)
        f.close()

        f = open(self.metaname(), 'w')
        m = meta(self._sha1)
        pickle.dump(m, f)
        f.close()

    def get_sha1(self):
        f = open(self.metaname())
        m = pickle.load(f)
        close(f)

    def chunks(self):
        f = open(self.filename(), 'r', 32*1024)
        for r in f:
            yield r

        f.close()
            
