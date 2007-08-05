from __future__ import absolute_import

from django.db import models
from django.db.models import permalink, Q
from django.conf.urls.defaults import patterns, include

import string, re
from imagestore.namespace import xhtml
from imagestore import restlist
from imagestore.urls import base_url

tagroot = None

__all__ = [ 'Tag' ]

class Tag(models.Model):

    word = models.CharField(maxlength=50, db_index=True)
    scope = models.ForeignKey('self', db_index=True)
    description = models.CharField(maxlength=100, null=True)

    # Tags may be geo-located
    #lat = models.FloatField(null=True)
    #long = models.FloatField(null=True)

    def __str__(self):
        return self.canonical()

    def depth(self):
        depth = 1
        if self.scope != tagroot:
            depth += self.scope.depth()
        return depth

    def tagpath(self):
        ret = []
        tag = self
        while tag != tagroot:
            ret.insert(0, tag)
            tag = tag.scope

        return ret

    def canonical(self):
        if not hasattr(self, '_canonical'):
            self._canonical = ':%s' % ':'.join([ t.word for t in self.tagpath() ])
        return self._canonical

    def __hash__(self):
        return hash(':'.join([ t.word for t in self.tagpath() ]) + (self.description or ''))

    def get_absolute_url(self):
        return '%stag/%s/' % (base_url(), self.canonical())

    def _render_full(self, ns):
        scope = self
        tags = []
        while scope != tagroot:
            tags.extend([ ns.a(scope.word, href=scope.get_absolute_url()), ':' ])
            scope = scope.scope

        tags.reverse()

        return ns.span(*tags)

    def _render_html(self, ns=xhtml):
        if self.description is not None:
            return ns.dfn({'title': self.canonical()}, self.description)
        else:
            return self.canonical()
        
    def is_more_specific(self, other):
        " Return true if this tag is more specific than other "

        tag = self
        while tag is not None:
            print 'tag=%s other=%s' % (tag, other)
            tag = tag.scope
            if tag == other:
                return True

        return False

    def more_specific(self):
        " Return list of all tags more specific than this one "
        expand = [ self ]
        ret = []

        while expand:
            ret.extend(expand)
            next = []
            for t in expand:
                next.extend(Tag.objects.filter(scope=t))
            expand = next

        return ret

    @staticmethod
    def tag(fulltag, create=False):
        assert tagroot is not None
        
        # canonicalize
        fulltag = string.strip(fulltag, u' :')

        tags = re.split(':+', fulltag)
        scope = tagroot
        for t in tags:
            if create:
                tag, created = Tag.objects.get_or_create(scope=scope, word=t)
            else:
                try:
                    tag = Tag.objects.get(scope=scope, word=t)
                except Tag.DoesNotExist:
                    return None
                
            scope = tag

        return scope
    
    class Meta:
        unique_together=(('scope', 'word'),)

    class Admin:
        pass

def tagroot_setup():
    (root, created) = Tag.objects.get_or_create(word='')

    root.scope = root
    root.save()

    for t in Tag.objects.filter(scope__isnull=True):
        t.scope = root
        t.save()

    return root
tagroot = tagroot_setup()


def get_url_tag(kwargs):
    tag = kwargs.get('tag', None)
    if tag is None:
        return None

    t = Tag.tag(tag)
    if t is None:
        raise Tag.DoesNotExist('Tag %s does not exist' % tag)

    return t

class TagEntry(restlist.Entry):
    __slots__ = [ 'tag' ]
    
    def __init__(self, tag=None):
        super(TagEntry, self).__init__()
        if tag:
            self.tag = tag

    def urlparams(self, kwargs):
        self.tag = get_url_tag(kwargs)

    def title(self, ns):
        t = self.tag
        return '%s' % (t.description or t.canonical())

    def rendertag(self, ns):
        return (ns.a(self.tag.canonical(),
                     href=self.tag.get_absolute_url()),
                self.tag.description or '')

    def _render_html(self, ns):
        from imagestore.picture import picturefeed, Picture
        t = self.tag

        ms = t.more_specific()
        
        return ns.dl(ns.dt('canonical'),
                     ns.dd(t._render_full(ns)),
                     ns.dt('sub-tags'),
                     ns.dd(ns.ul([ ns.li(ns.a(tt.word, href=tt.get_absolute_url()))
                                   for tt in t.tag_set.all() ])),
                     ns.dt('pictures'),
                     ns.dd(ns.a('%d pictures tagged' % t.picture_set.count(),
                                href=picturefeed.get_search_url(t.canonical()))),
                     ns.dd(ns.a('%d pictures sub-tagged' % Picture.objects.filter(tags__in = ms).distinct().count(),
                                href=picturefeed.get_search_url(t.canonical()+'*'))),
                     ns.dd('%d cameras tagged' % t.cameratags_set.count())
                     )

    
class TagList(restlist.List):
    def urlparams(self, kwargs):
        from imagestore.user import get_url_user

        self.urluser = get_url_user(kwargs)

    def title(self, ns):
        if self.urluser:
            return ns.span(ns.a('%s\'s' % self.urluser.username.capitalize(),
                                href=self.urluser.get_profile().get_absolute_url()), ' tags')
        else:
            return 'Tags'

    @permalink
    def get_absolute_url(self):
        return ('imagestore.tag.taglist', (), {})

    def filter(self):
        if self.urluser:
            return Q(picture__owner = self.urluser)
            
        return Q()

    def entries(self):
        """ Generate a list of all tags.  Tags are only considered to
        exist if there's a visible picture visible to the current user
        tagged with that tag."""
        from imagestore.picture import Picture

        to = Tag.objects.distinct().filter(self.filter())

        result = set()

        # Picture's direct tags
        result |= set(to.filter(picture__visibility = Picture.PUBLIC))
        result |= set(to.filter(picture__visibility = Picture.PRIVATE,
                                picture__owner = self.authuser))

        # This should be something like:
        # to.filter(picture__visibility = Picture.RESTRICTED,
        #           picture__owner__friends__user = self.authuser)
        # but this doesn't seem to work
        result |= set(to.extra(where=['imagestore_tag.id = imagestore_picture_tags.tag_id',
                                      'imagestore_picture_tags.picture_id = imagestore_picture.id',
                                      'imagestore_picture.visibility=%s',
                                      'imagestore_picture.owner_id = auth_user.id',
                                      'auth_user.id = imagestore_userprofile.user_id',
                                      'imagestore_userprofile.id = imagestore_userprofile_friends.userprofile_id',
                                      'imagestore_userprofile_friends.user_id=%s'],
                               tables=['imagestore_picture_tags',
                                       'imagestore_picture',
                                       'auth_user',
                                       'imagestore_userprofile',
                                       'imagestore_userprofile_friends'],
                               params=[Picture.RESTRICTED, self.authuser.id]))

        # Picture's camera tags
        result |= set(to.filter(cameratags__camera__picture__visibility = Picture.PUBLIC))
        result |= set(to.filter(cameratags__camera__picture__visibility = Picture.PRIVATE,
                                cameratags__camera__picture__owner = self.authuser))

        # Should be:
        # to.filter(cameratags__camera__picture__visibility = Picture.RESTRICTED,
        #           cameratags__camera__picture__owner__friends__user = self.authuser)
        # but...
        result |= set(to.extra(where=['imagestore_tag.id = imagestore_cameratags_tags.tag_id',
                                      'imagestore_cameratags_tags.cameratags_id = imagestore_cameratags.id',
                                      'imagestore_cameratags.camera_id = imagestore_camera.id',
                                      'imagestore_camera.id = imagestore_picture.camera_id',
                                      'imagestore_picture.visibility = %s',
                                      'imagestore_picture.owner_id = auth_user.id',
                                      'auth_user.id = imagestore_userprofile.user_id',
                                      'imagestore_userprofile.id = imagestore_userprofile_friends.userprofile_id',
                                      'imagestore_userprofile_friends.user_id = %s' ],
                               tables=['imagestore_cameratags_tags',
                                       'imagestore_cameratags',
                                       'imagestore_camera',
                                       'imagestore_picture',
                                       'auth_user',
                                       'imagestore_userprofile',
                                       'imagestore_userprofile_friends' ],
                               params=[Picture.RESTRICTED, self.authuser.id]))
        
        result = list(result)
        result.sort(lambda a,b: cmp(a.canonical(), b.canonical()))
        
        return [ TagEntry(t) for t in result ]

    def _render_html(self, ns, *args, **kwargs):
        ret = ns.dl({'class': 'tags'})
        for e in self.generate():
            dt,dd = e.rendertag(ns)
            ret.append(ns.dt({'class': 'tag'}, dt))
            ret.append(ns.dd({'class': 'tagdesc'}, dd))
        return ret

class TagComplete(TagList):
    def urlparams(self, kwargs):
        super(TagComplete,self).urlparams(kwargs)
        self.tagword = kwargs.get('tagpart')

    def filter(self):
        return Q(word__startswith=self.tagword) & super(TagComplete, self).filter()
        
taglist = TagList()
tag = TagEntry()
tagcomplete = TagComplete()
usertaglist = TagList()
usertagcomplete = TagComplete()

urlpatterns = patterns('',
                       ('^$',                               taglist),
                       ('^(?P<tag>(:[a-zA-Z0-9_ -]+)+)/$',  tag),
                       ('^(?P<tagpart>[a-zA-Z0-9_ -]+)/$',  tagcomplete),
                       )
