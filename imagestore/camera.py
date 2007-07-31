from __future__ import absolute_import

import string

from django.db import models
from django.db.models import permalink
from django.contrib.auth.models import User
from django.conf.urls.defaults import patterns, include

from imagestore.tag import Tag
from imagestore.namespace import xhtml
from imagestore.user import get_url_user
from imagestore.htmllist import HtmlList, HtmlEntry
from imagestore import microformat
from imagestore.daterange import daterange

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

class CameraList(HtmlList):
    __slots__ = [ 'urluser' ]

    def urlparams(self, kwargs):
        self.urluser = get_url_user(kwargs)

    def entries(self, **kwargs):
        return [ CameraEntry(c).render() for c in self.urluser.camera_set.all() ]

class CameraEntry(HtmlEntry):
    __slots__ = [ 'camera', 'urluser' ]
    
    def __init__(self, camera = None):
        HtmlEntry.__init__(self)
        if camera:
            self.camera = camera

    def urlparams(self, kwargs):
        self.urluser = get_url_user(kwargs)
        self.camera = get_url_camera(self.urluser, kwargs)
        
    def render(self):
        from imagestore.picture import PictureSearchFeed
        c = self.camera

        def format_ct(ct):
            return [ xhtml.dt(microformat.html_daterange(ct.daterange())),
                     xhtml.dd(xhtml.ul([ xhtml.li(t.render()) for t in ct.tags.all() ])) ]

        u = c.owner
        up = c.owner.get_profile()
        
        return xhtml.div({'class': 'camera' },
                         xhtml.h2(xhtml.a({'class': 'nickname', 'href': c.get_absolute_url() },
                                          c.nickname), ' - ',
                                  xhtml.span({'class': 'make'}, c.make), ', ',
                                  xhtml.span({'class': 'model'}, c.model)),
                         xhtml.dl(xhtml.dt('make'), xhtml.dd(c.make),
                                  xhtml.dt('model'), xhtml.dd(c.model),
                                  xhtml.dt('serial'), xhtml.dd(c.serial),
                                  xhtml.dt('owner'), xhtml.dd(xhtml.a({'href': up.get_absolute_url()},
                                                                      u.username)),
                                  xhtml.dt('pictures taken'),
                                  xhtml.dd(xhtml.a({'href': up.get_search_url('camera:%s' % c.nickname)},
                                                   str(c.picture_set.count()))),
                                  xhtml.dt('keywords'),
                                  xhtml.dd(xhtml.dl(*[ format_ct(ct)
                                                       for ct in c.cameratags_set.all() ]))))

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
        c = c.filter(serial=serial)
        
    if c.count() == 0:
        nick = string.join(model.lower().strip().split(), '-')

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

    def __str__(self):
        return '%s: %s' % (self.daterange(), self.tags.all())

    def daterange(self):
        return daterange(self.start, self.end)

    class Meta:
        ordering = [ 'start' ]

__all__ = [ 'Camera', 'get_camera', 'CameraTags' ]

cameralist      = CameraList()
camera          = CameraEntry()

urlpatterns = \
  patterns('',
           ('^$',                               cameralist),
           ('^(?P<camnick>[a-zA-Z0-9_-]+)/',    camera),
           )
