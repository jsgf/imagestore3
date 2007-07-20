import sha, md5
from django.db import models

class Media(models.Model):
    _chunksize = 64 * 1024
    
    sha1hash = models.CharField(maxlength=40, db_index=True)
    sequence = models.PositiveIntegerField()
    data = models.TextField(blank=True)

    def chunks(self):
        """A generator for all the chunks corresponding to a particular hash."""
        for c in Media.objects.filter(sha1hash=self.sha1hash):
            yield c.data

    def verify(self):
        """Verify that the chunks for a particular hash are all present and correct"""
        sha1 = sha.new()
        
        for d in self.chunks():
            sha1.update(d)

        return sha1.digest().encode('hex') == self.sha1hash

    @staticmethod
    def get(hash):
        return Media.objects.get(sha1hash=hash, sequence=0)

    @staticmethod
    def deletechunks(hash):
        """Delete all media chunks for a particular hash"""
        for m in Media.objects.filter(sha1hash=hash):
            m.delete()

    @staticmethod
    def store(data, hash=None):
        """Store a piece of data as media chunks"""
        if hash is None:
            sha1 = sha.new(data)
            hash = sha1.digest().encode('hex')

        old = Media.objects.filter(sha1hash=hash)
        if old.count() != 0:
            old = old[0]
            if old.verify():
                return old
            else:
                Media.deletechunks(hash)

        media = None
        order = 0
        while len(data) > 0:
            m = Media(data=data[:Media._chunksize], sha1hash=hash, sequence=order)
            m.save()
            data = data[Media._chunksize:]
            order += 1
            if media is None:
                media = m

        return media
    
    class Meta:
        ordering = [ 'sequence' ]
        unique_together = (('sha1hash', 'sequence'),)


