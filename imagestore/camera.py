from __future__ import absolute_import

import string

from ElementBuilder import Namespace, ElementTree
from cStringIO import StringIO

from django.db import models
from django.db.models import permalink
from django.contrib.auth.models import User
from django.conf.urls.defaults import patterns, include

from imagestore import microformat, restlist
from imagestore.tag import Tag
from imagestore.namespace import xhtml, html, timeline
from imagestore.user import get_url_user
from imagestore.daterange import daterange
from imagestore.rest import RestBase, serialize_xml

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

def render_timeline(camtags):
    def fmt(dt):
        return dt.strftime('%b %d %Y %T')

    def xmlstring(et):
        s = StringIO()
        ElementTree(et).write(s)
        return s.getvalue()

    def ct_title(ct):
        return ct.title or ', '.join([ t.description or t.canonical()
                                       for t in ct.tags.all()[:4] ])

    ret = timeline.data([ timeline.event(xmlstring(ct.html(html)),
                                         start = fmt(ct.start),
                                         end = fmt(ct.end),
                                         title = '%s: %s' % (ct.camera.nickname,
                                                             ct_title(ct)),
                                         isDuration = 'true')
                          for ct in camtags ])

    return ret    

class CameraList(restlist.List):
    __slots__ = [ 'urluser' ]

    def __init__(self, *args, **kwargs):
        super(CameraList, self).__init__(*args, **kwargs)
        self.add_type('timeline', 'application/xml', serialize_xml)

    def urlparams(self, kwargs):
        self.urluser = get_url_user(kwargs)

    def title(self, ns):
        if self.urluser:
            return ns.span(ns.a('%s\'s' % self.urluser.username,
                                href=self.urluser.get_profile().get_absolute_url()), ' cameras')
        else:
            return 'cameras'

    def render_timeline(self, *args, **kwargs):
        camtags = CameraTags.objects.all()
        
        if self.urluser:
            camtags = camtags.filter(camera__owner = self.urluser)

        return render_timeline(camtags)

    def entries(self, **kwargs):
        cameras = Camera.objects.all()
        if self.urluser:
            cameras = cameras.filter(owner=self.urluser)
            
        return [ CameraEntry(c, request=self.request) for c in cameras ]

class CameraEntry(restlist.Entry):
    __slots__ = [ 'camera', 'urluser' ]
    
    def __init__(self, camera = None, request = None):
        super(CameraEntry,self).__init__()
        self.add_type('timeline', 'application/xml', serialize_xml)
        if camera:
            self.camera = camera

        if request:
            self.request = request

    def urlparams(self, kwargs):
        self.urluser = get_url_user(kwargs)
        self.camera = get_url_camera(self.urluser, kwargs)

    def title(self, ns):
        return self.camera.nickname

    def generate(self):
        c = self.camera
        u = c.owner
        up = c.owner.get_profile()
        
        return { 'nickname':    c.nickname,
                 'url':         c.get_absolute_url(),
                 'make':        c.make,
                 'model':       c.model,
                 'serial':      c.serial,
                 'owner':       u.username,
                 'pictures':    { 'count':      c.picture_set.count(),
                                  'search':     up.get_search_url('camera:%s' % c.nickname) },
                 'keywords':    c.cameratags_set.all(),
                 }

    def render_timeline(self, *args, **kwargs):
        camtags = CameraTags.objects

        if self.urluser:
            camtags = camtags.filter(camera__owner = self.urluser)
        camtags = camtags.filter(camera = self.camera)

        return render_timeline(camtags)
    
    def render_json(self, *args, **kwargs):
        return self.generate()

    def _render_html(self, ns, *args, **kwargs):
        c = self.camera
        
        def format_ct(ct):
            return [ ns.dt(microformat.html_daterange(ct.daterange())),
                     ns.dd(ns.ul([ ns.li(t.render()) for t in ct.tags.all() ])) ]

        u = c.owner
        up = c.owner.get_profile()
        
        return ns.div({'class': 'camera' },
                      ns.h2(ns.a({'class': 'nickname',
                                  'href': self.append_url_params(c.get_absolute_url()) },
                                 c.nickname), ' - ',
                            ns.span({'class': 'make'}, c.make), ', ',
                            ns.span({'class': 'model'}, c.model)),
                      ns.dl(ns.dt('make'), ns.dd(c.make),
                            ns.dt('model'), ns.dd(c.model),
                            ns.dt('serial'), ns.dd(c.serial),
                            ns.dt('owner'), ns.dd(ns.a({'href': self.append_url_params(up.get_absolute_url())},
                                                       u.username)),
                            ns.dt('pictures taken'),
                            ns.dd(ns.a({'href': self.append_url_params(up.get_search_url('camera:%s' % c.nickname))},
                                       str(c.picture_set.count()))),
                            ns.dt(ns.a('keywords', href=c.get_absolute_url() + 'tag/')),
                            ns.dd(ns.dl(*[ format_ct(ct)
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
    tags = models.ManyToManyField(Tag)

    # start and end are always UTC
    start = models.DateTimeField(db_index=True, core=True)
    end = models.DateTimeField(core=True)

    #timezone = models.IntegerField("Timezone of camera's clock withing a time range",
    #                               null=True)
    title = models.CharField(maxlength=127, blank=True)
    
    def __str__(self):
        return '%s: %s' % (self.daterange(), self.tags.all())

    def daterange(self):
        return daterange(self.start, self.end)

    def html(self, ns=xhtml):
        return ns.div(ns.ul([ ns.li(t.render(ns=ns)) for t in self.tags.all() ]))

    @permalink
    def get_absolute_url(self):
        return ('imagestore.camera.cameratag',
                (self.camera.owner.username, self.camera.nickname, self.id),
                { 'user': self.camera.owner.username,
                  'camnick': self.camera.nickname,
                  'camtagid': self.id })

    class Meta:
        ordering = [ 'start' ]

def get_url_cameratag(camera, kwargs):
    id = kwargs.get('camtagid', None)
    if id is None:
        return None

    return CameraTags.objects.get(id=id, camera=camera)

class CameraTagEntry(restlist.Entry):
    def __init__(self, cameratag=None):
        super(CameraTagEntry, self).__init__()
        if cameratag:
            self.cameratag = cameratag
        
    def urlparams(self, kwargs):
        self.urluser = get_url_user(kwargs)
        self.camera = get_url_camera(self.urluser, kwargs)
        self.cameratag = get_url_cameratag(self.camera, kwargs)

    def title(self, ns):
        return ns.span(ns.a('%s\'s' % self.camera.nickname,
                            href=self.camera.get_absolute_url()),
                       ' tags for ',
                       ns.a('%s-%s' % (self.cameratag.start, self.cameratag.end),
                            href=self.cameratag.get_absolute_url()))

    def _render_html(self, ns):
        ct = self.cameratag
        return [ ns.dt(ns.a(microformat.html_daterange(ct.daterange()),
                            href=self.cameratag.get_absolute_url())),
                 ns.dd(ns.ul([ ns.li(t.render()) for t in ct.tags.all() ])) ]
        
class CameraTagList(restlist.List):
    def urlparams(self, kwargs):
        self.urluser = get_url_user(kwargs)
        self.camera = get_url_camera(self.urluser, kwargs)

    def title(self, ns):
        return ns.span('Tags for ', ns.a('%s\'s' % self.urluser.username,
                                         href=self.urluser.get_profile().get_absolute_url()),
                       ' ', ns.a(self.camera.nickname, href=self.camera.get_absolute_url()))

    def generate(self):
        return [ CameraTagEntry(ct) for ct in self.camera.cameratags_set.all() ]

__all__ = [ 'Camera', 'get_camera', 'CameraTags' ]

cameralist      = CameraList()
camerauserlist  = CameraList()
camerataglist   = CameraTagList()
cameratag       = CameraTagEntry()
camera          = CameraEntry()

urlpatterns = \
  patterns('',
           ('^$',                                       cameralist),
           ('^(?P<camnick>[a-zA-Z0-9_-]+)/$',           camera),
           ('^(?P<camnick>[a-zA-Z0-9_-]+)/tag/$',       camerataglist),
           ('^(?P<camnick>[a-zA-Z0-9_-]+)/tag/(?P<camtagid>[0-9]+)/$',       cameratag),
           )
