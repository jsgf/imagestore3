from __future__ import absolute_import

import sha, md5
import string, re
import types
from cStringIO import StringIO
import datetime as dt

from django.db import models
from django.db.models import permalink, Q
from django.http import (HttpRequest, HttpResponse,
                         HttpResponseForbidden, HttpResponseNotFound, Http404)
from django.contrib.auth.models import User
from django.conf.urls.defaults import patterns, include
from django.core.exceptions import ObjectDoesNotExist

from ElementBuilder import Namespace, ElementTree

from imagestore.media import Media
from imagestore.tag import Tag
from imagestore.rest import (RestBase, HttpResponseBadRequest,
                             HttpResponseConflict, HttpResponseBadRequest,
                             HttpResponseContinue, HttpResponseExpectationFailed,
                             serialize_xml)
from imagestore import urn, EXIF, image, microformat, restlist

from imagestore.atomfeed import AtomFeed, AtomEntry, atomtime, atomperson
from imagestore.namespace import atom, imst, html, xhtml, opensearch, timeline
from imagestore.daterange import daterange
from imagestore.search import SearchParser

__all__ = [ 'Picture' ]

class FilteredPictures(models.Manager):
    @staticmethod
    def visibility_filter(user):
        """ Returns a filter to limit the pictures visible
            to a particular authenticated user """
        vis = Q(visibility=Picture.PUBLIC)
        
        if user is not None:
            if user.is_superuser:
                vis = Q()
            else:
                up = user.get_profile()
                vis = vis | (Q(visibility=Picture.RESTRICTED, owner__in=up.friends) |
                             Q(visibility=Picture.PRIVATE, owner=user))

        return vis

    def vis_filter(self, authuser, *args, **kwargs):
        return self.filter(self.visibility_filter(authuser), *args, **kwargs)

    def vis_get(self, authuser, *args, **kwargs):
        return self.get(self.visibility_filter(authuser), *args, **kwargs)

class NotDeletedPictures(FilteredPictures):
    def get_query_set(self):
        return super(NotDeletedPictures, self).get_query_set().filter(deleted=False)

class Picture(models.Model):
    PUBLIC=0
    RESTRICTED=1
    PRIVATE=2

    def __init__(self, *args, **kwargs):
        self._camera_tags_query = None  # cache tags query
        super(Picture,self).__init__(*args, **kwargs)

    @staticmethod
    def str_visibility(v):
        return { Picture.PUBLIC: 'public',
                 Picture.RESTRICTED: 'restricted',
                 Picture.PRIVATE: 'private' }[v]

    objects = NotDeletedPictures()
    all_objects = FilteredPictures()

    @staticmethod
    def get(user, id):
        return Picture.objects.vis_get(user, id=id)

    sha1hash = models.CharField("unique sha1 hash of picture",
                                maxlength=40, db_index=True, unique=True, editable=False)
    mimetype = models.CharField("mime type for picture", maxlength=40, editable=False)

    md5hash = models.CharField("unique md5 hash of picture",
                               maxlength=32, db_index=True, unique=True, editable=False)
    datasize = models.PositiveIntegerField("raw picture size in bytes", editable=False)

    derived_from = models.ForeignKey('self', null=True, related_name='derivatives')

    width = models.PositiveIntegerField(editable=False)
    height = models.PositiveIntegerField(editable=False)
    orientation = models.PositiveIntegerField()

    created_time = models.DateTimeField("time picture was taken", db_index=True)
    uploaded_time = models.DateTimeField("time picture was uploaded",
                                         auto_now_add=True, db_index=True)
    modified_time = models.DateTimeField("time picture was last modified",
                                         auto_now=True, db_index=True)

    original_ref = models.CharField("external reference for picture",
                                    maxlength=100, blank=True)

    deleted = models.BooleanField('picture is logically deleted',
                                  editable=True, default=False)
    
    camera = models.ForeignKey('Camera', null=True,
                               verbose_name="camera which took this picture")
    owner = models.ForeignKey(User, related_name='pictures')
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

    def get_title(self, generate=True):
        """ Make a valiant attempt to return a title.  First choice is
        the image title itself.  If that's missing, then try to find a
        cameratag title.  Failing that, generate one."""
        if self.title:
            return self.title

        ct = self.camera.cameratags_set
        ct = ct.filter(start__lte=self.created_time, end__gt=self.created_time)
        ct = ct.exclude(title='').order_by('-start')
        if ct.count() != 0:
            return ct[0].title

        if generate:
            return 'Untitled #%d' % self.id
        return ''

    def mediakey(self, variant='orig'):
        if variant == 'orig':
            return '%d/%s' % (self.id, variant)
        else:
            return '%d/%s.%d' % (self.id, variant, self.orientation)
    
    def media(self, variant='orig'):
        return Media.get(self.mediakey(variant))
    
    def image(self, size):
        return image.ImageProcessor(self, size)

    def __str__(self):
        return '%d: %s' % (self.id, self.get_title())

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

    def get_exif_url(self):
        return '%sexif/' % self.get_absolute_url()

    def get_derivatives_url(self):
        return '%sderived/' % self.get_absolute_url()

    def get_comment_url(self):
        return '%scomment/' % self.get_absolute_url()

    def render_img(self, size='thumb', ns=xhtml):
        img = self.image(size)
        width, height = img.dimensions()
        return ns.img(src=self.get_picture_url(size),
                      width=str(width), height=str(height),
                      alt=self.description or self.get_title(),
                      title=self.get_title())

    def chunks(self, variant='orig'):
        return self.media(variant).chunks()

    def get_urn(self):
        return 'urn:picture:%d' % self.id

    # XXX the user here doesn't really matter, since this is just a redirection service
    urn.register('picture', lambda urn: Picture.get(user=None, id=int(urn[0])))

    def exif(self):
        img = string.join([ v for v in self.chunks() ], '')
        return EXIF.process_file(StringIO(img))

    def tags_query(self):
        """ Returns Tag query to select this picture's tags. """
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
        if self._camera_tags_query is None:
            q = Tag.objects.filter(self.camera_tags_query())
            q = q.distinct().order_by('id')
            self._camera_tags_query = q
            
        return self._camera_tags_query

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
    def canon_tags(tags, create=False):
        ''' Given a string containing ',' or ';' separated tags,
        return a list of properly canonicalized tags '''
        if type(tags) is types.StringType:
            tags = [ t.strip().lower() for t in re.split(' *[,;]+ *', tags) ]

        return [ type(t) is types.StringType and Tag.tag(t, create) or t
                 for t in tags if t is not None ]
                
    def add_tags(self, tags):
        for t in self.canon_tags(tags, create=True):
            self.tags.add(t)

    def del_tags(self, tags):
        for t in self.canon_tags(tags, create=False):
            self.tags.remove(t)

def get_url_picture(authuser, kwargs):
    id = kwargs.get('picid', None)
    if id is None:
        return None

    return Picture.get(authuser, int(id))

def picture_upload(self, owner, **kwargs):
    request = self.request
    
    def test_exists(sha1):
        try:
            # unfiltered visibility OK here, since unique is unique
            p = Picture.objects.get(sha1hash = sha1)
            return True
        except:
            return False

    client_sha1 = request.POST.get('sha1hash', None)

    file = request.FILES.get('image')
    if file is None:
        # Implement "look before you leap".  If the client gives
        # us a hash but no image data, and expects a continue
        # response, then check to see if the hash matches any
        # existing image, to save them from having to upload the
        # data before finding that out.
        expect = request.META.get('HTTP_EXPECT', None)
        print 'client_sha1=%s expect="%s"' % (client_sha1, expect)
        if (client_sha1 is not None and
            expect is not None and
            expect.startswith("100-")):
            if test_exists(client_sha1):
                return HttpResponseExpectationFailed('Picture %s already exists\n' % client_sha1)
            return HttpResponseContinue('OK, continue\n')
        return HttpResponseBadRequest('Need image data\n')

    # XXX allow unauthenticated uploads for now
    if owner is None: # != self.authuser:
        return HttpResponseForbidden('Need owner for image\n')

    data = file['content']
    type = file['content-type']
    filename = file['filename']

    sha1 = sha.new(data)
    hash = sha1.digest().encode('hex')

    # Make sure they provided a consistent hash
    if client_sha1 and hash != client_sha1:
        return HttpResponseBadRequest('provided sha1 (%s) != data sha1 (%s)\n' % (client_sha1, hash))

    if test_exists(hash):
        return HttpResponseConflict('Picture %s already exists\n' % hash)

    title = request.POST.get('title', '')

    file = StringIO(data)
    p = image.importer(file, owner=owner, title=title,
                       original_ref=filename,
                       sha1hash=hash, visibility=Picture.PUBLIC,
                       mimetype=type, **kwargs)

    if 'tags' in request.POST:
        p.add_tags(request.POST['tags'])

    entry = PictureEntry(p)
    entry.request = self.request
    entry.determine_format(self.format)
    
    resp = self.make_response(entry.render(format=self.format))
    resp['Location'] = p.get_absolute_url()
    resp.status_code = 201         # created

    return resp
        

class PictureEntry(AtomEntry):
    __slots__ = [ 'picture', 'urluser' ]
    
    def __init__(self, p = None, request=None):
        AtomEntry.__init__(self)

        if request is not None:
            self.request = request

        if p is not None:
            self.picture = p

    def title(self, ns):
        return self.picture.get_title()

    def urlparams(self, kwargs):
        from imagestore.user import get_url_user
        
        self.picture = get_url_picture(self.authuser, kwargs)
        self.urluser = get_url_user(kwargs)

    def get_last_modified(self):
        return self.picture.modified_time

    def get_Etag(self):
        p = self.picture
        return '%s %s' % (p.sha1hash, p.modified_time.isoformat())

    def _render_html(self, ns, *args, **kwargs):
        p = self.picture
        assert p is not None

        size = 'tiny'
        img = p.image(size)
        (width, height) = img.dimensions()

        htmltags = ns.ul([ ns.li(ns.a({ 'href':
                                        self.append_url_params(PictureFeed(search=tag.canonical()).get_absolute_url()) },
                                      tag._render_html(ns)))
                           for tag in p.effective_tags() ])

        html_derivatives = []
        if p.derivatives.count() != 0:
            html_derivatives = [ ns.dt(ns.a({ 'href':p.get_derivatives_url() }, 'Derivatives')),
                                 ns.dd(ns.ul([ ns.li(ns.a({'href': self.append_url_params(deriv.get_absolute_url()) },
                                                          '%d: %s' % (deriv.id, deriv.get_title())))
                                               for deriv in p.derivatives.all() ])) ]

        photog = ''
        if p.photographer is not None:
            photog = [ ns.dt('Photographer'), ns.dd(microformat.hcard(p.photographer)) ]

        derived_from = []
        if p.derived_from is not None:
            derived_from = [ ns.dt('Derived from'),
                             ns.dd(ns.a({'href': self.append_url_params(p.derived_from.get_absolute_url())},
                                        '%d: %s' % (p.derived_from.id,
                                                    p.derived_from.get_title()))) ]


        content = [ ns.div({'class': 'image' },
                           ns.a({'href': self.append_url_params(p.get_absolute_url())},
                                p.render_img(ns=ns))),
                    ns.dl({ 'class': 'metadata' },
                          ns.dt('Owner' ),
                          ns.dd({'class': 'owner' }, microformat.hcard(p.owner)),
                          photog,
                          derived_from,
                          html_derivatives,
                          ns.dt('Taken'),
                          ns.dd({'class': 'created-time'},
                                microformat.html_datetime(p.created_time)),
                          ns.dt('Uploaded'),
                          ns.dd({'class': 'uploaded-time'},
                                microformat.html_datetime(p.uploaded_time)),
                          ns.dt('Modified'),
                          ns.dd({'class': 'modified-time'},
                                microformat.html_datetime(p.modified_time)),
                          ns.dt('Orientation'),
                          ns.dd({'class': 'orientation'},
                                str(p.orientation)),
                          ns.dt('Visibility'),
                          ns.dd(ns.dfn({'class': 'visibility',
                                        'title': str(p.visibility) },
                                       Picture.str_visibility(p.visibility))),
                          ns.dt('Camera'),
                          ns.dd(ns.a({'href': self.append_url_params(p.camera.get_absolute_url(), remove='format')},
                                     p.camera.nickname),
                                ' ',
                                ns.a({'href': self.append_url_params(p.get_exif_url(), remove='format')}, 'Exif')),
                          ns.dt({'class': 'tags'}, 'Tags'),
                          ns.dd(htmltags),
                          ns.dt('Description'),
                          ns.dd(ns.p(p.description)),
                          ),

                    ns.a({'href': self.append_url_params(p.get_comment_url())},
                         '%d comments' % p.comment_set.count()) ]
        
        return content
    
    def render_atom(self):
        p = self.picture
        assert p is not None

        def atomcat(t):
            attr = { 'term': t.canonical() }
            if t.description:
                attr['label'] = t.description

            return atom.category(attr)

        atomtags = [ atomcat(tag) for tag in p.effective_tags() ]

        related = [ atom.link({'rel': 'related',
                               'href': deriv.get_absolute_url(),
                               'class': 'derivative' })
                    for deriv in p.derivatives.all() ]

        content = self._render_html(xhtml)

        ret = atom.entry(atom.id(self.picture.get_urn()),
                         atom.title(p.get_title()),
                         atom.author(atomperson(p.owner)),
                         atom.updated(atomtime(p.modified_time)),
                         atom.published(atomtime(p.created_time)),
                         imst.uploaded(atomtime(p.uploaded_time)),
                         imst.visibility(Picture.str_visibility(p.visibility)),
                         imst.orientation(str(p.orientation)),
                         atomtags,
                         atom.link({'rel': 'comments', 'href': p.get_comment_url() }),
                         atom.link({'rel': 'self', 'href': p.get_absolute_url()}),
                         related,
                         atom.content({ 'type': 'xhtml' }, xhtml.div(*content))
                         )
        if p.camera:
            ret.append(atom.link({ 'rel': 'camera', 'href': p.camera.get_absolute_url() }))

        return ret

# Should this be just another format for picture?
class PictureExif(restlist.Entry):
    __slots__ = [ 'picture' ]
    
    def urlparams(self, kwargs):
        self.picture = get_url_picture(self.authuser, kwargs)
        
    def get_last_modified(self):
        return self.picture.modified_time

    def get_Etag(self):
        return '%s exif' % self.picture.sha1hash

    def title(self, ns):
        return ns.span('Exif for ', ns.a('"%s"' % self.picture.get_title(),
                                         href=self.picture.get_absolute_url()))

    def render_json(self):
        exif = {}
        for k,v in self.picture.exif().items():
            if k != 'JPEGThumbnail':
                exif[(k, v.tag)] = v.values
        return exif

    def _render_html(self, ns):
        return microformat.exif(self.picture.exif(), ns=ns)

class PictureSizeList(restlist.Entry):
    def urlparams(self, kwargs):
        self.picture = get_url_picture(self.authuser, kwargs)

    def title(self, ns):
        return ns.span('Sizes for ', ns.a('%s' % self.picture.get_title(),
                                          href=self.picture.get_absolute_url()))

    def generate(self):
        p = self.picture

        ret = []
        for size,width,height in image.Image.get_sizes():
            img = image.ImageProcessor(p, size)
            (w,h) = img.dimensions()    # actual width and height

            ret.append((size, w, h, p.get_picture_url(size)))

        return ret

    def render_json(self):
        return self.generate()
    
    def _render_html(self, ns):
        p = self.picture
        return ns.div(ns.ol([ ns.li(ns.a({ 'href': url }, '%s: %dx%d' % (size, w, h)))
                              for size,w,h,url in self.generate() ]))
        
class PictureImage(RestBase):
    """ Return the actual bits of a picture """

    __slots__ = [ 'picture', 'size' ]
    
    def __init__(self):
        self.size = None
        super(PictureImage, self).__init__()

    def urlparams(self, kwargs):
        self.picture = get_url_picture(self.authuser, kwargs)
    
    def get_Etag(self):
        if self.size is None:
            return None
        
        m = self.picture.media(self.size)
        ret = None
        if m is not None:
            ret = '%s' % m.sha1hash
        return ret

    def get_content_length(self):
        if self.size is None:
            return None
        
        m = self.picture.media(self.size)
        ret = None
        if m is not None:
            ret = m.size
        print '%d.%s = %s' % (self.picture.id, self.size, ret)
        return ret

    def get_last_modified(self):
        if self.size is None:
            return None
        
        m = self.picture.media(self.size)
        ret = None
        if m is not None:
            ret = m.update_time
        print '%d.%s = %s' % (self.picture.id, self.size, ret)
        return ret
    
    def do_GET(self, *args, **kwargs):
        p = self.picture

        size = kwargs.get('size', 'orig')
        
        if size == '':
            size = 'orig'

        self.size = size
        m = p.media(size)

        image = p.image(size)
        
        if m is None:
            (m, type) = image.generate()
            
        if m is None:
            return HttpResponseNotFound('image %d has no size "%s"' % (p.id, size))

        self.format = 'image'
        self.mimetype = image.mimetype()

        ret = HttpResponse(m.chunks(), mimetype=image.mimetype())

        # Make sure saving the image gives a useful filename
        ret['Content-Disposition'] = ('inline; filename="%d-%s.%s"' %
                                      (p.id, size, image.extension))

        return ret
        
class PictureFeed(AtomFeed):
    __slots__ = [ 'urluser', '_query', 'search' ]

    def __init__(self, search=None):
        super(PictureFeed, self).__init__()

        self.urluser = None

        self.search = search
        self.query = None
        
        self._query = None
        self.add_type('timeline', 'application/xml', serialize_xml)

    def title(self, ns):
        if self.search:
            return 'Pictures: "%s": %d results' % (self.search, self.results().count())
        else:
            return '%d Pictures' % self.results().count()

    @permalink
    def get_absolute_url(self):
        if self.search:
            return ('imagestore.picture.picturesearch',
                    [ self.urluser, self.search ],
                    { 'search': self.search, 'urluser': self.urluser })
        else:
            return ('imagestore.picture.picturefeed',
                    [ self.urluser ],
                    { 'urluser': self.urluser })

    def get_search_url(self, search):
        if not self.search:
            return '%s-/%s/' % (self.get_absolute_url(), search)
        else:
            return '%s%s/' % (self.get_absolute_url(), search)
        

    def urlparams(self, kwargs):
        from imagestore.user import get_url_user

        self.urluser = get_url_user(kwargs)
        self.search = kwargs.get('search', '')
        if self.search is not None:
            self.search = self.search.strip(' /+')
            self.query = SearchParser(self.search).query

    def filter(self):
        filter = Q()
        
        if self.urluser is not None:
            print 'filtering user %s' % self.urluser.username
            filter = filter & Q(owner = self.urluser)

        if self.query is not None:
            filter = filter & self.query

        return filter
    
    def preamble(self, ns):
        """ Insert a little html form for as a guide for how to post
            to this channel; it should really be a proper APP thing."""
        form = xhtml.form({'method': 'post', 'action': '',
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
        links = self.alt_links(ns)
        p = self.link_prev()
        if p:
            links.append(ns.link(rel="prev", type=self.mimetype, href=p))
        n = self.link_next()
        if n:
            links.append(ns.link(rel="next", type=self.mimetype, href=n))

        return links + [form]
            

    def results(self, order=None):
        if self._query is None or order :
            q = Picture.objects.vis_filter(self.authuser, self.filter())
            q = q.distinct().select_related()
            if order:
                q = q.order_by(order)
            self._query = q
            
        return self._query

    def limits(self):
        start = 0
        limit = 50
        try:
            limit = int(self.request.GET.get('limit', str(limit)))
            limit = min(limit, 200)
        except ValueError:
            pass

        try:
            start = int(self.request.GET.get('start', str(start)))
        except ValueError:
            pass
        
        return (start,limit)

    def get_last_modified(self):
        res = self.results().order_by('-modified_time')
        if res.count() > 0:
            return res[0].modified_time
        return None
    
    def opensearch(self):
        count = self.results().count()
        start,limit = self.limits()

        return [ opensearch.totalResults(str(count)),
                 opensearch.startIndex(str(start)),
                 opensearch.itemsPerPage(str(limit)) ]

    def entries(self, **kwargs):
        order = None

        orders = {
            'id': 'id',
            'created': 'created_time',
            'uploaded': 'uploaded_time',
            'modified': 'modified_time',
            'random': '?'
            }

        default = '-created'
        order = self.request.GET.get('order', default)

        if order[0] == '-' and order[1:] in orders:
            order = '-' + orders[order[1:]]
        elif order in orders:
            order = orders[order]
        else:
            order = default

        start,limit = self.limits()
        res = self.results(order)

        return [ PictureEntry(p, request=self.request) for p in res[start : start+limit] ]


    def link_prev(self):
        start,limit = self.limits()

        if start > 0:
            return self.append_url_params('', { 'start': max(0,start-limit), })

    def link_next(self):
        start,limit = self.limits()
        count = self.results().count()
        
        if start+limit < count:
            return self.append_url_params('', { 'start': start+limit })

    def _render_html(self, ns, *args, **kwargs):
        start,limit = self.limits()

        nav = ns.span({'class': 'nav'})

        p = self.link_prev()
        if p:
            nav.append(ns.a({'href': p, 'class': 'prev'}, 'Prev'))

        n = self.link_next()
        if n:
            nav.append(ns.a({'href': n, 'class': 'next'}, 'Next'))

        return ns.div(nav, ns.ul([ ns.li(e._render_html(ns, *args, **kwargs))
                                   for e in self.generate() ]))

    def render_timeline(self, *args, **kwargs):
        def fmt(dt):
            return dt.strftime('%a %b %d %Y %T')

        def xmlstring(et):
            s = StringIO()
            ElementTree(et).write(s)
            return s.getvalue()
        tl = timeline.data()
        
        res = self.results('created_time')

        prev = None
        evt = None
        count = 0
        for p in res:
            if (prev is None or
                (p.created_time - prev.created_time) > dt.timedelta(minutes=30)):
                if evt is not None and count > 1:
                    evt.attrib['title'] += ' (%d pics)' % count
                count = 0
                evt = timeline.event('',
                                     start=fmt(p.created_time),
                                     title=p.get_title(generate=False),
                                     icon=p.get_picture_url('icon'))
                tl.append(evt)
            prev = p
            count += 1
            d = html.div()
            if count > 1 and p.title:
                d.append(html.h3(p.title))
            d.append(html.p(p.render_img('tiny', ns=html)))
            evt.text += xmlstring(d)

        if evt is not None and count > 1:
            evt.attrib['title'] += ' (%d pics)' % count

        return tl

    def do_POST(self, *args, **kwargs):
        return picture_upload(self, owner=self.urluser)

class DerivedPictureFeed(PictureFeed):
    @permalink
    def get_absolute_url(self):
        return ('imagestore.picture.picturederived',
                [ self.basepic.id, self.search ],
                { 'picid': self.basepic.id, 'search': self.search })

    def urlparams(self, kwargs):
        super(DerivedPictureFeed,self).urlparams(kwargs)
        self.basepic = get_url_picture(self.authuser, kwargs)

    def filter(self):
        return super(DerivedPictureFeed, self).filter() & Q(derived_from = self.basepic)

    def do_POST(self, *args, **kwargs):
        print 'args=%s kwargs=%s' % (args, kwargs)
        return picture_upload(self, owner=self.urluser, derived_from=self.basepic)
    
class Comment(models.Model):
    comment = models.TextField()
    user = models.ForeignKey(User)
    picture = models.ForeignKey(Picture)
    created_time = models.DateTimeField(auto_now_add=True)
    modified_time = models.DateTimeField(auto_now=True)

    def __str__(self):
        return '%s: %s' % (user.username, comment)

class CommentFeed(AtomFeed):
    __slots__ = [ 'picture' ]
    
    def title(self, ns):
        return ns.span('Comments for ',
                       ns.a('#%d: %s' % (self.picture.id, self.picture.get_title()),
                            href=self.picture.get_absolute_url()))
                      

    def urlparams(self, kwargs):
        self.picture = get_url_picture(self.authuser, kwargs)

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

# Make a pile of distinct names so that reverse URL lookups work
picturefeed     = PictureFeed()
picturesearch   = PictureFeed()
picture         = PictureEntry()
pictureexif     = PictureExif()
picturesizelist = PictureSizeList()
pictureimage    = PictureImage()
picturederived  = DerivedPictureFeed()
commentfeed     = CommentFeed()
comment         = CommentEntry()

urlpatterns = \
  patterns('',
           ('^$',                       picturefeed),
           ('^-/(?P<search>.*)$',       picturesearch),
           
           ('(?P<picid>[0-9]+)/$',                                      picture),
           ('(?P<picid>[0-9]+)/exif/$',                                 pictureexif),
           ('(?P<picid>[0-9]+)/derived/(?:-/(?P<search>.*))?$',         picturederived),
           ('(?P<picid>[0-9]+)/pic/$',                                  picturesizelist),
           ('(?P<picid>[0-9]+)/pic/(?P<size>[a-z]*)(?:\.[a-z]*)/?$',    pictureimage),
           ('(?P<picid>[0-9]+)/comment/$',                              commentfeed),
           ('(?P<picid>[0-9]+)/comment/(?P<commentid>[0-9]+)/?$',       comment),
           )
