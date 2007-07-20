from django.db import models
from django.contrib.auth.models import User

from imagestore.tag import Tag

class Camera(models.Model):
    owner = models.ForeignKey(User, edit_inline=models.TABULAR)

    nickname = models.CharField(maxlength=32, core=True)
    make = models.CharField(maxlength=32, core=True)
    model = models.CharField(maxlength=64, core=True)
    serial = models.CharField(maxlength=128, blank=True)

    def get_absolute_url(self):
        return '%scamera/%s/' % (self.owner.get_absolute_url(), self.nickname)

    class Meta:
        unique_together=(('owner', 'nickname'),)

    class Admin:
        pass

class CameraTags(models.Model):
    """ Sets a set of implicit tags for a camera for a date range.  If
    a picture is taken with a particular camera on date X, then any
    tags applied to the Camera covering that date will be implicitly
    applied to that picture."""
    
    camera = models.ForeignKey(Camera)
    start = models.DateTimeField()
    end = models.DateTimeField()
    tags = models.ManyToManyField(Tag)
