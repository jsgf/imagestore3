from __future__ import absolute_import

import sha, md5
from django.db import models

class Media(models.Model):
    _chunksize = 64 * 1024

    key = models.CharField(maxlength=128, db_index=True)
    sha1hash = models.CharField(maxlength=40, db_index=True)
    size = models.PositiveIntegerField()
    cache = models.BooleanField("temporary cache value")
    update_time = models.DateTimeField(auto_now=True)

    def verify(self):
        """Verify that the chunks for a particular hash are all present and correct"""
        sha1 = sha.new()
        
        for d in self.chunks.all():
            sha1.update(d.data)

        return sha1.digest().encode('hex') == self.sha1hash

    def chunks(self):
        return ( c.data for c in self.mediachunks.all() )

    @staticmethod
    def get(key):
        try:
            ret = Media.objects.get(key=key)
        except Media.DoesNotExist:
            ret = None
        return ret
    
    @staticmethod
    def store(key, data, sha1hash=None, cache=False):
        """Store a piece of data as media chunks"""

        old = Media.get(key)
        if old is not None:
            if not old.verify():
                old.chunks.delete()
            else:
                return old
            
        if sha1hash is None:
            sha1 = sha.new(data)
            sha1hash = sha1.digest().encode('hex')

        media = Media(key=key, sha1hash=sha1hash, cache=cache, size=len(data))
        media.save()
        
        seq = 0
        while len(data) > 0:
            #print 'storing key=%s seq=%d' % (key, seq)
            m = MediaChunk(media=media, sequence=seq,
                           data=data[:Media._chunksize])
            m.save()
            data = data[Media._chunksize:]
            seq += 1

        return media

class MediaChunk(models.Model):
    media = models.ForeignKey(Media, related_name='mediachunks')
    data = models.TextField(blank=True)
    sequence = models.PositiveIntegerField()

    class Meta:
        ordering = [ 'sequence' ]
        unique_together = (('id', 'sequence'),)

__all__ = [ 'Media' ]
