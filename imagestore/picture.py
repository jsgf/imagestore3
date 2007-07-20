import sha, md5
from cStringIO import StringIO
from datetime import datetime
from xml.etree.cElementTree import ElementTree

from django.db import models
from django.db.models import Q
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden, Http404
from django.contrib.auth.models import User
from django.conf.urls.defaults import patterns, include

from imagestore.media import Media
from imagestore.camera import Camera
from imagestore.tag import Tag
import imagestore.EXIF as EXIF

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

    media = models.ForeignKey(Media, related_name='pictures')
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    orientation = models.PositiveIntegerField()

    thumbnail = models.ForeignKey(Media, related_name='thumbnails')
    th_width = models.PositiveSmallIntegerField("thumbnail width")
    th_height = models.PositiveSmallIntegerField("thumbnail height")

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

    tags = models.ManyToManyField(Tag, verbose_name=('tags'))

    class Meta:
        ordering = [ 'created_time' ]

    class Admin:
        pass

    def get_absolute_url(self):
        return '/image/%d/' % self.id

    def get_medium_url(self):
        return '%spic/medium.jpg' % self.get_absolute_url()

    def get_comment_url(self):
        return '%scomments/' % self.get_absolute_url()

    def picture_chunks(self):
        return Media.chunks(self.media)

    def get_thumbnail(self):
        return string.join(Media.chunks(self.thumbnail), '')

    def effective_tags(self):
        pass

    @staticmethod
    def insert(owner, visibility, type, imagedata, **kwarg):
        print 'insert imagedata=%d' % len(imagedata)
        m = Media.store(imagedata)

        try:
            md5hash = md5.new()
            md5hash.update(imagedata)
            p = Picture(sha1hash = m.sha1hash,
                        mimetype = type,
                        md5hash = md5hash.digest().encode('hex'),
                        media = m,
                        datasize = len(imagedata),
                        orientation = 0,
                        owner = owner,
                        visibility = visibility,
                        **kwarg)
            p.save()
        except Exception, e:
            print 'Insert failed: %s' % e
            Media.deletechunks(m.sha1hash)
            raise e
            
        return p

    @staticmethod
    def insert_jpeg(owner, visibility, imagedata, **kwarg):
        exif = EXIF.process_file(StringIO(imagedata))

        created_time = datetime.now()
        
        for k in [ 'EXIF DateTimeDigitized',
                   'EXIF DateTimeOriginal',
                   'Image DateTime' ]:
            if k in exif.keys():
                created_time = datetime.strptime(exif[k].values, '%Y:%m:%d %H:%M:%S')
                break

        thumbnail = exif.get('JPEGThumbnail')
        th = None
        if thumbnail is not None:
            th = Media.store(thumbnail)
            
        return Picture.insert(owner, visibility, 'image/jpeg', imagedata,
                              created_time=created_time,
                              thumbnail=th,
                              th_width=10, th_height=10, width=10, height=10)

class Comment(models.Model):
    comment = models.TextField()
    user = models.ForeignKey(User)
    picture = models.ForeignKey(Picture)
    created_time = models.DateTimeField(auto_now_add=True)
    modified_time = models.DateTimeField(auto_now=True)

    def __str__(self):
        return '%s: %s' % (user.username, comment)

class PictureEntry(AtomEntry):
    def __init__(self, p = None):
        self.pic = p

    def getpic(self):
        if self.pic is not None:
            return self.pic

        picid = self.kwargs['picid']

        try:
            self.pic = Picture.objects.get(id=picid)
        except Picture.DoesNotExist:
            pass

        return self.pic

    def render(self):
        p = self.getpic()
        if p is None:
            raise Http404()
        
        ret = atom.entry(atom.uri(u'urn:sha1:%s' % self.pic.sha1hash),
                         atom.title(p.title),
                         atom.author(atomperson(p.owner)),
                         atom.summary(xhtml.h3(p.title),
                                      xhtml.a({ 'href': p.get_absolute_url() },
                                              xhtml.img({'src': p.get_medium_url() }))),
                         atom.updated(atomtime(p.modified_time)),
                         imst.created(atomtime(p.created_time)),
                         imst.uploaded(atomtime(p.uploaded_time)),
                         atom.link({'rel': 'comments', 'href': p.get_comment_url() }),
                         atom.content({ 'src': p.get_absolute_url(),
                                        'type': p.mimetype }))
        if p.camera:
            ret.append(atom.link({ 'rel': 'camera', 'href': p.camera.get_absolute_url() }))

        return ret
    
class PictureFeed(AtomFeed):
    def __init__(self):
        AtomFeed.__init__(self, title='Pictures')

    def filter(self, kwargs):
        filter = Q()

        if self.user is not None:
            filter = filter & (Q(owner = self.user) |
                               Q(photographer = self.user))

        return filter

    def entries(self, **kwargs):
        filter = self.filter(kwargs)
        return [ PictureEntry(p) for p in Picture.objects.filter(filter) ]
    
    def do_POST(self, *args, **kwargs):
        file = self.request.FILES.get('image')
        if file is None:
            return HttpResponseConflict('Need image data\n')

        if self.user is None:
            return HttpResponseForbidden('Need owner for image\n')

        image = file['content']
        type = file['content-type']
        
        sha1 = sha.new()
        sha1.update(image)
        hash = sha1.digest().encode('hex')

        try:
            p = Picture.objects.get(sha1hash = hash)
            return HttpResponseConflict('Image %d:%s already exists\n' %
                                        (p.id, p.sha1hash))
        except Picture.DoesNotExist:
            pass
        
        p = Picture.insert_jpeg(self.user, Picture.PUBLIC, image,
                                title=self.request.POST.get('title'))

        entry = PictureEntry(p)
        entry.request = self.request
        ret = entry.do_GET()
        ret['Location'] = p.get_absolute_url()
        
        return ret

urlpatterns = patterns('',
                       ('^$',                   PictureFeed()),
                       ('^-/(?P<search>.*)$',   PictureFeed()),
                       ('^--/(?P<summary>.*)$', PictureFeed()),
                       ('(?P<picid>[0-9]+)/',   PictureEntry()),
                       )
