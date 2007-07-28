from __future__ import absolute_import

import string

from django.db import models
from django.db.models import permalink
from django.contrib.auth.models import User
from django.conf.urls.defaults import patterns, include

from imagestore.tag import Tag
from imagestore.atomfeed import AtomFeed, AtomEntry
from imagestore.namespace import atom, xhtml
from imagestore.user import get_url_user

class Camera(models.Model):
    owner = models.ForeignKey(User, edit_inline=models.TABULAR)

    nickname = models.CharField(maxlength=32, core=True)
    make = models.CharField(maxlength=32, core=True)
    model = models.CharField(maxlength=64, core=True)
    serial = models.CharField(maxlength=128, blank=True)

    def __str__(self):
        return '%s' % self.nickname

    @permalink
    def get_absolute_url(self):
        return ('imagestore.camera.camera',
                (self.owner.username, self.nickname),
                { 'camnick': self.nickname, 'user': self.owner.username })

    class Meta:
        unique_together=(('owner', 'nickname'),)

    class Admin:
        pass

def get_url_camera(user, kwargs):
    id = kwargs.get('camnick', None)
    if id is None:
        return None

    return Camera.objects.get(owner=user, nickname = id)

class CameraFeed(AtomFeed):
    __slots__ = [ 'urluser' ]

    def urlparams(self, kwargs):
        self.urluser = get_url_user(kwargs)

    def entries(self, **kwargs):
        return [ CameraEntry(c) for c in self.urluser.camera_set.all() ]

class CameraEntry(AtomEntry):
    __slots__ = [ 'camera', 'urluser' ]
    
    def __init__(self, camera = None):
        AtomEntry.__init__(self)
        if camera:
            self.camera = camera

    def urlparams(self, kwargs):
        self.urluser = get_url_user(kwargs)
        self.camera = get_url_camera(self.urluser, kwargs)
        
    def render(self):
        c = self.camera
        
        return atom.entry(atom.title('%s - %s' % (c.nickname, c.model)),
                          atom.content({ 'type': 'xhtml' },
                                       xhtml.div(xhtml.p('%d pictures taken' %
                                                         c.picture_set.count()))
                                       )
                          )

def get_camera(owner, exif):
    try:
        make = str(exif['Image Make'])
        model = str(exif['Image Model'])
    except KeyError:
        return None

    serial = None
    for s in ('MakerNote SerialNumber', 'MakerNote CameraSerialNumber'):
        if s in exif:
            serial = exif[s]
            break

    c = Camera.objects.filter(owner=owner, make=make, model=model)
    if serial is not None:
        c.filter(serial=serial)
        
    if c.count() == 0:
        nick = string.join(model.lower().strip().split(), '')

        c = Camera(owner=owner, nickname=nick,
                   make=make, model=model, serial=serial or '')
        c.save()
    else:
        c = c[0]

    return c

class CameraTags(models.Model):
    """ Sets a set of implicit tags for a camera for a date range.  If
    a picture is taken with a particular camera on date X, then any
    tags applied to the Camera covering that date will be implicitly
    applied to that picture."""
    
    camera = models.ForeignKey(Camera, edit_inline=models.STACKED)
    start = models.DateTimeField(db_index=True, core=True)
    end = models.DateTimeField(core=True)
    tags = models.ManyToManyField(Tag)

    class Meta:
        ordering = [ 'start' ]

__all__ = [ 'Camera', 'get_camera', 'CameraTags' ]

camerafeed      = CameraFeed()
camera          = CameraEntry()

urlpatterns = \
  patterns('',
           ('^$',                               camerafeed),
           ('^(?P<camnick>[a-zA-Z0-9_-]+)/',    camera),
           )
