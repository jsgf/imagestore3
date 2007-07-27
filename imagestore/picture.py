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

class NotDeletedPictures(models.Manager):
    def get_query_set(self):
        return super(NotDeletedPictures, self).get_query_set().filter(deleted=False)

class Picture(models.Model):
    PUBLIC=0
    RESTRICTED=1
    PRIVATE=2

    objects = NotDeletedPictures()
    all_objects = models.Manager()

    sha1hash = models.CharField("unique sha1 hash of picture",
                                maxlength=40, db_index=True, unique=True, editable=False)
    mimetype = models.CharField("mime type for picture", maxlength=40, editable=False)

    md5hash = models.CharField("unique md5 hash of picture",
                               maxlength=32, db_index=True, unique=True, editable=False)
    datasize = models.PositiveIntegerField("raw picture size in bytes", editable=False)

    derived_from = models.ForeignKey('self', null=True, related_name='derivatives')

    def mediakey(self, variant='orig'):
        if variant == 'orig':
            return '%d/%s' % (self.id, variant)
        else:
            return '%d/%s.%d' % (self.id, variant, self.orientation)
    
    def media(self, variant='orig'):
        return Media.get(self.mediakey(variant))
    
    def image(self, size):
        return image.ImageProcessor(self, size)

    width = models.PositiveIntegerField(editable=False)
    height = models.PositiveIntegerField(editable=False)
    orientation = models.PositiveIntegerField()

    created_time = models.DateTimeField("time picture was taken")
    uploaded_time = models.DateTimeField("time picture was uploaded",
                                         auto_now_add=True)
    modified_time = models.DateTimeField("time picture was last modified",
                                         auto_now=True)

    original_ref = models.CharField("external reference for picture",
                                    maxlength=100, blank=True)

    deleted = models.BooleanField('picture is logically deleted',
                                  editable=True, default=False)
    
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
    copyright = models.CharField(maxlength=100, blank=True)

    tags = models.ManyToManyField(Tag, verbose_name='tags')

    def __str__(self):
        return '%d: %s' % (self.id, self.title)

    class Meta:
        ordering = [ '-created_time' ]
        get_latest_by = [ '-created_time' ]

    class Admin:
        fields = (
            (None, {
            'fields': ('title', 'created_time', 'description', 'camera',
                       ('owner', 'photographer'), 'copyright', 'visibility', 'tags'),
            }),
            )

    @permalink
    def get_absolute_url(self):
        return ('imagestore.picture.picture', str(self.id), { 'picid': str(self.id) })

    def get_picture_url(self, size='thumb'):
        try:
            ext = '.%s' % self.image(size).extension
        except KeyError:
            ext = ''
        return '%spic/%s%s' % (self.get_absolute_url(), size, ext)

    def get_comment_url(self):
        return '%scomment/' % self.get_absolute_url()

    def chunks(self, variant='orig'):
        return self.media(variant).chunks()

    def get_urn(self):
        return 'urn:picture:%d' % self.id

    urn.register('picture', lambda urn: Picture.objects.get(id=int(urn[0])))

    def exif(self):
        img = string.join([ v for v in self.chunks() ], '')
        return EXIF.process_file(StringIO(img))

    def tags_query(self):
        ''' Returns Tag query to select this picture's tags. '''
        return Q(picture = self)

    def camera_tags_query(self):
        ''' Returns Tag query to return
            this's picture's camera tags. '''
        return (Q(cameratags__camera = self.camera) &
                Q(cameratags__start__lte = self.created_time) &
                Q(cameratags__end__gte = self.created_time))

    def camera_tags(self):
        """
        Return list of tags conferred on this picture by the camera it
        was taken with.
        """
        ct = Tag.objects.filter(self.camera_tags_query())
        ct = ct.distinct().order_by('id')
        
        return ct

    def effective_tags(self):
        """
        Return the list of all tags applied to this picture, directly
        and indirectly.
        """
        if False:
            # Doesn't work: Django bug?
            t = self.camera_tags_query() | self.tags_query()
            return Tag.objects.filter(t).distinct().order_by('id')
        else:
            ret = list(set(self.tags.all()) | set(self.camera_tags()))
            ret.sort(lambda a,b: cmp(a.id, b.id))
            return ret

    @staticmethod
    def canon_tags(tags):
        ''' Given a string containing ',' or ';' separated tags,
        return a list of properly canonicalized tags '''
        if type(tags) is types.StringType:
            tags = [ t.strip().lower() for t in re.split(' *[,;]+ *', tags) ]

        return [ type(t) is types.StringType and Tag.tag(t) or t
                 for t in tags ]
                
    def add_tags(self, tags):
        for t in self.canon_tags(tags):
            self.tags.add(t)

    def del_tags(self, tags):
        for t in self.canon_tags(tags):
            self.tags.remove(t)

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

        def atomcat(t):
            attr = { 'term': t.canonical() }
            if t.description:
                attr['label'] = t.description

            return atom.category(attr)

        atomtags = [ atomcat(tag) for tag in p.effective_tags() ]
        htmltags = xhtml.ul([ xhtml.li(tag.render()) for tag in p.effective_tags() ])

        photog = None
        if p.photographer is not None:
            photog = xhtml.p('Photographer:', microformat.hcard(p.photographer))

        html_derivatives = None
        if p.derivatives.count() != 0:
            html_derivatives = xhtml.p('Derivatives:',
                                       xhtml.ul([ xhtml.li(xhtml.a({'href': deriv.get_absolute_url() },
                                                                   '%d: %s' % (deriv.id, deriv.title)))
                                                  for deriv in p.derivatives.all() ]))

        derived_from = None
        if p.derived_from is not None:
            derived_from = xhtml.p(xhtml.a({'href': p.derived_from.get_absolute_url()},
                                           'Derived from %d: %s' % (p.derived_from.id,
                                                                    p.derived_from.title)))

        size = 'tiny'
        img = p.image(size)
        content = [ xhtml.a({'href': p.get_absolute_url()},
                            xhtml.img({'src': p.get_picture_url(size),
                                       'width': str(img.dimensions()[0]),
                                       'height': str(img.dimensions()[1]),
                                       'alt': p.title })),
                    xhtml.p('Owner:', microformat.hcard(p.owner)),
                    photog,
                    derived_from,
                    html_derivatives,
                    xhtml.span('Taken with: ',
                               xhtml.a({'href': p.camera.get_absolute_url()},
                                       p.camera.nickname)),
                    xhtml.p('Tags:', htmltags),
                    xhtml.a({'href': p.get_comment_url()},
                            '%d comments' % p.comment_set.count()) ]

        content = [ c for c in content if c is not None ]

        related = [ atom.link({'rel': 'related',
                               'href': deriv.get_absolute_url(),
                               'class': 'derivative' })
                    for deriv in p.derivatives.all() ]

        ret = atom.entry(atom.id(self.picture.get_urn()),
                         atom.title(p.title or 'untitled #%d' % p.id),
                         atom.author(atomperson(p.owner)),
                         atom.updated(atomtime(p.modified_time)),
                         atom.published(atomtime(p.created_time)),
                         imst.uploaded(atomtime(p.uploaded_time)),
                         atomtags,
                         atom.link({'rel': 'comments', 'href': p.get_comment_url() }),
                         atom.link({'rel': 'self', 'href': p.get_absolute_url()}),
                         related,
                         atom.content({ 'type': 'xhtml' }, xhtml.div(content))
                         )
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

        m = p.media(size)

        if m is None:
            (m, type) = p.image(size).generate()
            
        if m is None:
            return HttpResponseNotFound('image %d has no size "%s"' % (p.id, size))

        return HttpResponse(m.chunks(), mimetype=p.mimetype)
        
class PictureFeed(AtomFeed):
    def __init__(self):
        AtomFeed.__init__(self)

    def title(self):
        return 'Pictures'

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
                          xhtml.label({'for': 'up-image'}, 'Image'),
                          xhtml.input({'type': 'file', 'name': 'image',
                                       'accept': 'image/*', 'id': 'up-image'}),
                          xhtml.label({'for': 'up-title'}, 'Title'),
                          xhtml.input({'type': 'text', 'name': 'title',
                                       'id': 'up-image'}),
                          xhtml.label({'for': 'up-tags'}, 'Tags'),
                          xhtml.input({'type': 'text', 'name': 'tags',
                                       'id': 'iup-tags'}),
                          xhtml.input({'type': 'submit', 'name': 'upload',
                                       'value': 'Upload'}))

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
        filename = file['filename']
        
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
                           original_ref=filename,
                           sha1hash=hash, visibility=Picture.PUBLIC,
                           mimetype=type)

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
        AtomFeed.__init__(self)

    def title(self):
        return 'Comments for #%d: %s' % (self.picture.id, self.picture.title or 'untitled')

    def entries(self, **kwargs):
        return [ CommentEntry(c)
                 for c in Comment.objects.filter(picture=self.picture) ]

    @permalink
    def get_absolute_url(self):
        return ('imagestore.picture.commentfeed',
                (str(self.picture.id), ),
                { 'picid': str(self.picture.id) })
                  

class CommentEntry(AtomEntry):
    def __init__(self, comment=None):
        AtomEntry.__init__(self)
        if comment is not None:
            self.comment = comment

picturefeed     = PictureFeed()
picturesearch   = PictureFeed()
picturesummary  = PictureFeed()
picture         = PictureEntry()
pictureexif     = PictureExif()
pictureimage    = PictureImage()
commentfeed     = CommentFeed()
comment         = CommentEntry()

urlpatterns = \
  patterns('',
           ('^$',                       picturefeed),
           ('^-/(?P<search>.*)$',       picturesearch),
           ('^--/(?P<summary>.*)$',     picturesummary),
           
           ('(?P<picid>[0-9]+)/$',                                      picture),
           ('(?P<picid>[0-9]+)/exif/$',                                 pictureexif),
           ('(?P<picid>[0-9]+)/pic/(?P<size>[a-z]*)(?:\.[a-z]*)?/?$',   pictureimage),
           ('(?P<picid>[0-9]+)/comment/$',                              commentfeed),
           ('(?P<picid>[0-9]+)/comment/(?P<commentid>[0-9]+)/?$',       comment),
           )


__all__ = [ 'Picture', 'PictureFeed', 'PictureEntry', 'PictureImage', 'PictureExif',
            'Comment', 'CommentFeed', 'CommentEntry' ]
