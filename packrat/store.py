from __future__ import absolute_import

import sha, md5
import os, os.path
import glob
import cPickle as pickle

class Content(object):
    __slots__ = [ 'store', 'key', 'priv', 'meta' ]
    
    def __init__(self, store, key, priv):
        self.store = store
        self.key = key
        self.priv = priv

class ContentStore(object):
    def __init__(self):
        pass

    def create(self, key, priv, meta, data):
        pass

    def delete(self, key):
        pass

    def read(self, key):
        pass

class FileContent(Content):
    def __init__(self, store, key, priv):
        super(FileContent, self).__init__(store, key, priv)

    def datapath(self):
        return self.store.datapath(self.key, self.priv)

    def metapath(self):
        return self.store.metapath(self.key, self.priv)
        
    def read(self):
        return file(self.datapath(), 'rb').read()

    def readmeta(self):
        return pickle.load(file(self.metapath(), 'rb'))
        
    def writemeta(self, meta):
        pickle.dump(meta, file(self.metapath(), 'wb'), 2)
                    
    def url(self):
        if self.store.puburl and self.priv == 'public':
            return '%s/%s/data' % (self.store.puburl, self.key)

        return None

    def setpriv(self, priv):
        assert priv in ('public', 'private')

        old = self.store.path(self.key, self.priv)
        self.priv = priv
        new = self.store.path(self.key, self.priv)
        os.renames(old, new)

class FileContentStore(ContentStore):
    __slots__ = [ 'pubroot', 'privroot' ]
    
    def __init__(self, pubroot, privroot=None, puburl=None):
        if privroot is None:
            privroot = pubroot

        self.pubroot = pubroot
        self.privroot = privroot
        self.puburl = puburl

    def path(self, key, priv):
        assert priv in ('public', 'private')
        
        root = self.privroot
        if priv == 'public':
            root = self.pubroot

        return os.path.join(root, priv, key)

    def find(self, keyprefix):
        pub = [ ('public', os.path.basename(pub)) for pub in
                glob.glob('%s/public/%s*' % (self.pubroot, keyprefix)) ]
        priv = [ ('private', os.path.basename(priv)) for priv in
                glob.glob('%s/private/%s*' % (self.pubroot, keyprefix)) ]

        return pub + priv

    def datapath(self, key, priv):
        return os.path.join(self.path(key, priv), 'data')

    def metapath(self, key, priv):
        return os.path.join(self.path(key, priv), '__meta')

    def exists(self, key, priv):
        return os.path.exists(self.path(key, priv))

    def create(self, key, data, meta=None, priv='private', cache=False):
        path = self.path(key, priv)
        if not os.path.exists(path):
            os.makedirs(path)
            
        file(self.datapath(key, priv), 'wb').write(data)

        ret = self.get(key, priv)
        ret.writemeta(meta)

        return ret
        
    def get(self, key, priv):
        return FileContent(self, key, priv)
