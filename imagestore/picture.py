from __future__ import absolute_import

import sha, md5
import string, re
import types
from cStringIO import StringIO
from datetime import datetime
from xml.etree.cElementTree import ElementTree

from django.db import models
from django.db.models import Q, permalink
from django.http import (HttpRequest, HttpResponse, HttpResponseForbidden, HttpResponseNotFound,
                         Http404)
from django.contrib.auth.models import User
from django.conf.urls.defaults import patterns, include

from imagestore.media import Media
from imagestore.camera import Camera
from imagestore.tag import Tag
from imagestore.RestBase import RestBase

import imagestore.urn as urn
import imagestore.EXIF as EXIF
import imagestore.image as image
import imagestore.microformat as microformat

from imagestore.atomfeed import AtomFeed, AtomEntry, atomtime, atomperson, HttpResponseConflict
from imagestore.namespace import atom, imst, xhtml

class Picture(models.Model):
    PUBLIC=0
    RESTRICTED=1
    PRIVATE=2
    
    sha1hash = models.CharField("unique sha1 hash of picture",
                                maxlength=40, db_index=True, unique=True)
    mimetype = models.CharField("mime type for picture", maxlength=40)

    md5hash = models.CharField("unique md5 hash of picture",
                               maxlength=32, db_index=True, unique=True)
    datasize = models.PositiveIntegerField("raw picture size in bytes")

    derived_from = models.ForeignKey('self', null=True)

    def mediakey(self, variant='orig'):
        return '%d/%s' % (self.id, variant)
    
    def media(self, variant='orig'):
        return Media.get(self.mediakey(variant))
    
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    orientation = models.PositiveIntegerField()

    created_time = models.DateTimeField("time picture was taken")
    uploaded_time = models.DateTimeField("time picture was uploaded",
                                         auto_now_add=True)
    modified_time = models.DateTimeField("time picture was last modified",
                                         auto_now=True)

    original_ref = models.CharField("external reference for picture", maxlength=100)

    camera = models.ForeignKey(Camera, null=True,
                               verbose_name="camera which took this picture")
    owner = models.ForeignKey(User, related_name='owned_pics')
    visibility = models.PositiveSmallIntegerField("visibility rights of this picture",
                                                  db_index=True,
                                                  choices=((PUBLIC, 'Public'),
                                                           (RESTRICTED, 'Restricted'),
                                                           (PRIVATE, 'Private')),
                                                  radio_admin=True)
    photographer = models.ForeignKey(User, null=True,
                                     related_name='photographed_pics')
    title = models.CharField(maxlength=127, blank=True)
    description = models.TextField(blank=True)
    copyright = models.TextField(blank=True)

    tags = models.ManyToManyField(Tag, verbose_name='tags')

    class Meta:
        ordering = [ 'created_time' ]

    class Admin:
        pass

    @permalink
    def get_absolute_url(self):
        return ('imagestore.views.picture', str(self.id))

    def get_picture_url(self, size='thumbnail'):
        try:
            ext = '.%s' % image.extensions[self.mimetype]
        except KeyError:
            ext = ''
        return '%spic/%s%s' % (self.get_absolute_url(), size, ext)

    def get_comment_url(self):
        return '%scomments/' % self.get_absolute_url()

    def picture_chunks(self, variant='orig'):
        return self.media(variant).chunks()

    def get_thumbnail(self):
        m=Media.get(self.mediakey('thumb.%d' % self.orientation))
        return string.join(m.chunks(), '')

    def get_urn(self):
        return 'urn:picture:%d' % self.id

    def exif(self):
        img = string.join([ v for v in self.picture_chunks() ], '')
        return EXIF.process_file(StringIO(img))

    urn.register('picture', lambda urn: Picture.objects.get(id=int(urn[0])))

    def effective_tags(self):
        pass

    @staticmethod
    def canon_tags(tags):
        if type(tags) is types.StringType:
            tags = [ t.strip().lower() for t in re.split(' *[,;] *', tags) ]

        return [ type(t) is types.StringType and Tag.tag(t) or t
                 for t in tags ]
                
    def add_tags(self, tags):
        tags = self.canon_tags(tags)
        for t in tags:
            self.tags.add(t)

    def del_tags(self, tags):
        tags = self.canon_tags(tags)
        self.tags.remove(tags)

class PictureEntry(AtomEntry):
    def __init__(self, p = None):
        AtomEntry.__init__(self)
        if p is not None:
            self.picture = p

        if self.urluser is not None and self.urluser != p.owner:
            raise Http404

    def render(self):
        p = self.picture
        assert p is not None

#        tags = xhtml.ul({'class': 'tags'},
#                        [ xhtml.li(list(p.tags.all())) ])
        
        ret = atom.entry(atom.id(self.picture.get_urn()),
                         atom.title(p.title or 'untitled #%d' % p.id),
                         atom.author(atomperson(p.owner)),
                         atom.summary(xhtml.h3(p.title),
                                      xhtml.a({ 'href': p.get_absolute_url() },
                                              xhtml.img({'src': p.get_picture_url('medium') }))),
                         atom.updated(atomtime(p.modified_time)),
                         imst.created(atomtime(p.created_time)),
                         imst.uploaded(atomtime(p.uploaded_time)),
#                         tags,
                         atom.link({'rel': 'comments', 'href': p.get_comment_url() }),
                         atom.content({ 'src': p.get_absolute_url(),
                                        'type': p.mimetype }))
        if p.camera:
            ret.append(atom.link({ 'rel': 'camera', 'href': p.camera.get_absolute_url() }))

        return ret

class PictureExif(RestBase):
    def do_GET(self, *args, **kwargs):
        p = self.picture

        ret = HttpResponse(mimetype='application/xhtml+xml')
        ElementTree(microformat.exif(p.exif())).write(ret)

        return ret

class PictureImage(RestBase):
    def do_GET(self, *args, **kwargs):
        p = self.picture

        size = kwargs.get('size', 'orig')
        if size == '':
            size = 'orig'
            
        if size != 'orig' and size not in image.sizes:
            return HttpResponseNotFound('image %d has no size "%s"' % (p.id, size))
            
        m = p.media(size)

        if m is None:
            return HttpResponseNotFound("Can't generate '%s'" % size)

        return HttpResponse(m.chunks(), mimetype=p.mimetype)
        
class PictureFeed(AtomFeed):
    def __init__(self):
        AtomFeed.__init__(self, title='Pictures')

    def filter(self, kwargs):
        filter = Q()

        if self.urluser is not None:
            print 'filtering user %s' % self.urluser.username
            filter = filter & (Q(owner = self.urluser) |
                               Q(photographer = self.urluser))

        return filter
    
    def preamble(self):
        return xhtml.form({'method': 'post', 'action': '',
                           'enctype': 'multipart/form-data'},
                          xhtml.input({'type': 'file', 'name': 'image',
                                       'accept': 'image/*'}),
                          xhtml.input({'type': 'text', 'name': 'title'}),
                          xhtml.input({'type': 'text', 'name': 'tags'}),
                          xhtml.input({'type': 'submit', 'name': 'upload'}))

    def entries(self, **kwargs):
        filter = self.filter(kwargs)
        return [ PictureEntry(p) for p in Picture.objects.filter(filter) ]
    
    def do_POST(self, *args, **kwargs):
        file = self.request.FILES.get('image')
        if file is None:
            return HttpResponseConflict('Need image data\n')

        if self.urluser is None:
            return HttpResponseForbidden('Need owner for image\n')

        data = file['content']
        type = file['content-type']
        
        sha1 = sha.new()
        sha1.update(data)
        hash = sha1.digest().encode('hex')

        try:
            p = Picture.objects.get(sha1hash = hash)
            return HttpResponseConflict('Image %d:%s already exists\n' %
                                        (p.id, p.sha1hash))
        except Picture.DoesNotExist:
            pass

        title = self.request.POST.get('title')
        print 'title=%s' % title

        file = StringIO(data)
        p = image.importer(file, owner=self.urluser, title=title,
                           sha1hash=hash, visibility=Picture.PUBLIC, mimetype=type)

        if 'tags' in self.request.POST:
            p.add_tags(self.request.POST['tags'])

        entry = PictureEntry(p)
        entry.request = self.request
        ret = entry.do_GET()
        ret['Location'] = p.get_absolute_url()
        
        return ret

class Comment(models.Model):
    comment = models.TextField()
    user = models.ForeignKey(User)
    picture = models.ForeignKey(Picture)
    created_time = models.DateTimeField(auto_now_add=True)
    modified_time = models.DateTimeField(auto_now=True)

    def __str__(self):
        return '%s: %s' % (user.username, comment)

class CommentFeed(AtomFeed):
    def __init__(self):
        AtomFeed.__init__(self, title='Comments')

    def entries(self, **kwargs):
        return [ CommentEntry(p)
                 for p in Comment.objects.filter(picture=self.picture) ]

    @permalink
    def get_absolute_url(self):
        return ('imagestore.views.comments', { 'picid': self.picture.id })
                  

class CommentEntry(AtomEntry):
    def __init__(self):
        AtomEntry.__init__(self)

urlpatterns = \
  patterns('',
           ('^$',                   PictureFeed()),
           ('^-/(?P<search>.*)$',   PictureFeed()),
           ('^--/(?P<summary>.*)$', PictureFeed()),
           
           ('(?P<picid>[0-9]+)/$',            'imagestore.views.picture'),
           ('(?P<picid>[0-9]+)/exif/$',       'imagestore.views.exif'),
           ('(?P<picid>[0-9]+)/comments/$',   'imagestore.views.comments'),
           ('(?P<picid>[0-9]+)/pic/(?P<size>[a-z]*)(?:\.[a-z]*)?/?$', 'imagestore.views.pic_image'),
           )


__all__ = [ 'Picture', 'PictureFeed', 'PictureEntry', 'PictureImage', 'PictureExif',
            'Comment', 'CommentFeed', 'CommentEntry' ]
