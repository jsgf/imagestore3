from __future__ import absolute_import

import string, re

from django.db import models
from django.db.models import permalink, Q
from django.utils.text import capfirst
import django.newforms as forms
from django.conf.urls.defaults import patterns, include
from django.http import HttpResponseForbidden, HttpResponseRedirect

from .namespace import xhtml
from . import restlist
from .urls import base_url

tagroot = None

__all__ = [ 'Tag' ]

tagre = r'[^\d\W][\w_-]*'
c_tagre = re.compile(tagre+'$', re.U | re.I)

class TagField(models.ManyToManyField):
    def __init__(self, to, **kwargs):
        super(TagField,self).__init__(to, **kwargs)
        self.help_text = 'List keywords, separated by ","'
        
    def formfield(self, **kwargs):
        defaults = {'required': not self.blank, 'widget': TagWidget, 'label': capfirst(self.verbose_name), 'help_text': self.help_text }
        defaults.update(kwargs)
        return TagFormField(**defaults)

class TagFormField(forms.CharField):
    def clean(self, value):
        return [ tt for tt in [ Tag.tag(t, create=True) for t in re.split(' *[,;]+ *', value) ] if tt is not None ]

    def widget_attrs(self, widget):
        w = super(TagFormField,self).widget_attrs(widget) or {}
        w.update({'size': '50'})
        return w
    
class TagWidget(forms.TextInput):
    def render(self, name, value, attrs=None):
        value = ', '.join([ t.canonical() for t in value ])
        return super(TagWidget, self).render(name, value, attrs)

class Tag(models.Model):

    word = models.CharField(maxlength=50, db_index=True)
    scope = models.ForeignKey('self', db_index=True)
    description = models.CharField(maxlength=100, null=False, blank=True)

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

    def get_edit_url(self):
        return '%sedit/' % self.get_absolute_url()

    def _render_full(self, ns):
        scope = self
        tags = []
        while scope != tagroot:
            tags.extend([ ns.a(scope.word, href=scope.get_absolute_url()), ':' ])
            scope = scope.scope

        tags.reverse()

        return ns.span(*tags)

    def _render_html(self, ns=xhtml, *args, **kwargs):
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
        """
        Given a string, return a properly formed tag.  If "create"
        is true, create any necessary tags.

        Tags may not contain spaces; any spaces are squashed out.
        They must also match: [a-z][a-z0-9_-]*
        """
        assert tagroot is not None
        
        # canonicalize
        fulltag = string.strip(fulltag, u' :').lower()
        fulltag = string.replace(fulltag, ' ', '')
        tags = re.split(' *:+ *', fulltag)
                
        scope = tagroot
        for t in tags:
            if not c_tagre.match(t):
                return None
            
            if create:
                tag, created = Tag.objects.get_or_create(scope=scope, word=t)
            else:
                try:
                    tag = Tag.objects.get(scope=scope, word__iexact=t)
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

    def may_edit(self):
        return (self.tag != tagroot and
                self.authuser and
                self.authuser.has_perm('packrat.tag_change'))

    def urlparams(self, kwargs):
        self.tag = get_url_tag(kwargs)

    def title(self, ns):
        t = self.tag
        return ns.a('%s' % (t.description or t.canonical()),
                    href=t.get_absolute_url())

    def rendertag(self, ns):
        return (ns.a(self.tag.canonical(),
                     href=self.tag.get_absolute_url()),
                self.tag.description or '')

    def _render_html(self, ns, *args, **kwargs):
        from .picture import picturefeed, Picture
        t = self.tag

        ms = t.more_specific()
        
        ret = ns.dl(ns.dt('canonical'),
                    ns.dd(t._render_full(ns)),
                    ns.dt('sub-tags'),
                    ns.dd(ns.ul([ ns.li(ns.a(tt.word, href=tt.get_absolute_url()),
                                        tt.description and (' - %s' % tt.description) or '')
                                  for tt in t.tag_set.all() ])),
                    ns.dt('pictures'),
                    ns.dd(ns.a('%d pictures tagged' % t.picture_set.count(),
                               href=picturefeed.get_search_url(t.canonical()))),
                    ns.dd(ns.a('%d pictures sub-tagged' % Picture.objects.filter(tags__in = ms).distinct().count(),
                               href=picturefeed.get_search_url(t.canonical()+'*'))),
                    ns.dd('%d cameras tagged' % t.cameratags_set.count()),
                    )

        if self.may_edit():
            ret.append(ns.dt(ns.a('edit', href=t.get_edit_url())))

        return ret


class TagEdit(TagEntry):
    def form(self, ns):
        t = self.tag

        return ns.form({'action': '', 'method': 'post'},
                       ns.ul(ns.li(ns.label('Description',
                                            ns.input(type='text', size='100',
                                                     name='description',
                                                     value=t.description or ''))),
                             ns.li(ns.label('%s: ' % t.scope.canonical(),
                                            ns.input(type='text', size='20',
                                                     name='word', value=t.word))),
                             ns.li(ns.input(type='submit'))))

    def input_error(self, msg, status=400):
        self.status_code = status
        ns = xhtml
        return self._html_frame(ns, ns.p(msg, self.form(ns)))
    
    def do_POST(self, *args, **kwargs):
        t = self.tag

        if not self.may_edit():
            return HttpResponseForbidden('May not edit %s' % t.canonical())

        
        word = self.request.POST.get('word', '')
        desc = self.request.POST.get('description', '')

        desc = desc.strip()
        word = word.strip().lower()
        
        if word != t.word:
            newtag = Tag.tag('%s:%s' % (t.scope.canonical(), word), create=True)
            if newtag is None:
                return self.input_error('Word "%s" is badly formed' % word)

            if newtag.description:
                # Don't replace existing description
                desc = newtag.description

            if newtag != t:
                for p in t.picture_set.filter(owner=self.authuser):
                    p.tags.remove(t)
                    p.tags.add(newtag)

                for c in t.cameratags_set.filter(camera__owner=self.authuser):
                    c.tags.remove(t)
                    c.tags.add(newtag)
                
            t = newtag

        if t.description != desc:
            t.description = desc
            t.save()

        return HttpResponseRedirect(t.get_absolute_url())
    
    def _render_html(self, ns, *args, **kwargs):
        return self.form(ns)
    
    
class TagList(restlist.List):
    def urlparams(self, kwargs):
        from .user import get_url_user

        self.urluser = get_url_user(kwargs)

    def title(self, ns):
        if self.urluser:
            return ns.span(ns.a('%s\'s' % self.urluser.username.capitalize(),
                                href=self.urluser.get_profile().get_absolute_url()), ' tags')
        else:
            return 'Tags'

    @permalink
    def get_absolute_url(self):
        return ('packrat.tag.taglist', (), {})

    def filter(self):
        if self.urluser:
            return Q(picture__owner = self.urluser)
            
        return Q()

    def entries(self):
        """ Generate a list of all tags.  Tags are only considered to
        exist if there's a visible picture visible to the current user
        tagged with that tag."""
        from .picture import Picture

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
        if self.authuser:
            result |= set(to.extra(where=['packrat_tag.id = packrat_picture_tags.tag_id',
                                          'packrat_picture_tags.picture_id = packrat_picture.id',
                                          'packrat_picture.visibility=%s',
                                          'packrat_picture.owner_id = auth_user.id',
                                          'auth_user.id = packrat_userprofile.user_id',
                                          'packrat_userprofile.id = packrat_userprofile_friends.userprofile_id',
                                          'packrat_userprofile_friends.user_id=%s'],
                                   tables=['packrat_picture_tags',
                                           'packrat_picture',
                                           'auth_user',
                                           'packrat_userprofile',
                                           'packrat_userprofile_friends'],
                                   params=[Picture.RESTRICTED, self.authuser.id]))

        # Picture's camera tags
        result |= set(to.filter(cameratags__camera__picture__visibility = Picture.PUBLIC))
        result |= set(to.filter(cameratags__camera__picture__visibility = Picture.PRIVATE,
                                cameratags__camera__picture__owner = self.authuser))

        # Should be:
        # to.filter(cameratags__camera__picture__visibility = Picture.RESTRICTED,
        #           cameratags__camera__picture__owner__friends__user = self.authuser)
        # but...
        if self.authuser:
            result |= set(to.extra(where=['packrat_tag.id = packrat_cameratags_tags.tag_id',
                                          'packrat_cameratags_tags.cameratags_id = packrat_cameratags.id',
                                          'packrat_cameratags.camera_id = packrat_camera.id',
                                          'packrat_camera.id = packrat_picture.camera_id',
                                          'packrat_picture.visibility = %s',
                                          'packrat_picture.owner_id = auth_user.id',
                                          'auth_user.id = packrat_userprofile.user_id',
                                          'packrat_userprofile.id = packrat_userprofile_friends.userprofile_id',
                                          'packrat_userprofile_friends.user_id = %s' ],
                                   tables=['packrat_cameratags_tags',
                                           'packrat_cameratags',
                                           'packrat_camera',
                                           'packrat_picture',
                                           'auth_user',
                                           'packrat_userprofile',
                                           'packrat_userprofile_friends' ],
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
tagedit = TagEdit()
tagcomplete = TagComplete()
usertaglist = TagList()
usertagcomplete = TagComplete()

urlpatterns = patterns('',
                       ('^$',                               taglist),
                       ('^(?P<tag>(:%s)+)/$' % tagre,       tag),
                       ('^(?P<tag>(:%s)+)/edit/$' % tagre,  tagedit),
                       ('^(?P<tagpart>%s)/$' % tagre,       tagcomplete),
                       )
