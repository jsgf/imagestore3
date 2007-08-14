from __future__ import absolute_import

from django.db import models
from django.db.models import permalink
from django.contrib.auth.models import User
from django.conf.urls.defaults import patterns, include
from django.http import HttpResponseForbidden, HttpResponseRedirect

from .rest import HttpResponseBadRequest, HttpResponseConflict
from .atomfeed import AtomFeed, AtomEntry
from .user import get_url_user
from .namespace import html
from .picture import PictureFeed, get_url_search
from .json import extract_attr
from .search import ParseException

class View(models.Model):
    name = models.CharField(maxlength=40, blank=False)
    description = models.CharField(maxlength=80)
    
    search = models.TextField("search query for view")
    order = models.CharField(maxlength=16, blank=True)
    limit = models.PositiveIntegerField(default=100)
    
    owner = models.ForeignKey(User)

    class Meta:
        unique_together=(('owner', 'name'),)

    @permalink
    def get_absolute_url(self):
        return ('packrat.view.view',
                (self.owner.username, self.name),
                { 'user': self.owner.username,
                  'viewname': self.name })

    def may_edit(self, authuser):
        return self.owner == authuser

def get_url_view(user, kwargs):
    id = kwargs.get('viewname', None)
    if id is None:
        return None

    return View.objects.get(owner = user, name = id)

class ViewEntry(AtomEntry):
    __slots__ = [ 'view', 'urluser', 'search' ]
    
    def __init__(self, view=None, *args, **kwargs):
        super(ViewEntry, self).__init__(*args, **kwargs)
        if view is not None:
            self.view = view
        self.search = ''
        
    def urlparams(self, kwargs):
        self.urluser = get_url_user(kwargs)
        self.view = get_url_view(self.urluser, kwargs)
        try:
            self.search = get_url_search(self.request, kwargs)
        except ParseException, e:
            return self.render_error(error=400,  # bad request
                                     title='Error parsing search query',
                                     body=html.blockquote(e.message))

    def jsonize(self):
        ret = extract_attr(self.view, [ 'id', 'name', 'description', 'search', 'order', 'limit' ])
        ret['url'] = self.view.get_absolute_url()
        return ret

    def title(self, ns):
        v = self.view
        return '%s: %s' % (v.name, v.description)

    def get_feed(self):
        v = self.view        
        order = self.request.GET.get('order', v.order)
        limit = self.request.GET.get('limit', v.limit)

        search = '%s/%s' % (v.search, self.search)

        return PictureFeed(search=search, order=order, limit=limit, proto=self)

    def _render_html(self, ns, *args, **kwargs):
        return self.get_feed()._render_html(ns, *args, **kwargs)

    def render_summary(self, ns, *args, **kwargs):
        v = self.view
        return ns.span(ns.a(v.name, href=v.get_absolute_url()), ' - %s' % (v.description or v.search))

    def render_json(self, *args, **kwargs):
        return self.get_feed().render_json(*args, **kwargs)

    def render_atom(self, *args, **kwargs):
        return self.get_feed().render_atom(*args, **kwargs)

    def do_POST(self, *args, **kwargs):
        v = self.view
        if not v.may_edit(self.authuser):
            return HttpResponseForbidden('Cannot delete view "%s" for %s' % (v.name, self.urluser.username))
        
        POST = self.request.POST
        
        v.search = POST.get('search', v.search)
        v.description = POST.get('description', v.description)
        v.order = POST.get('order', v.order)
        v.limit = POST.get('limit', v.limit)
        v.name = POST.get('viewname', v.name)

        v.save()

        return HttpResponseRedirect(v.get_absolute_url())
        
    def do_DELETE(self, *args, **kwargs):
        v = self.view
        if not v.may_edit(self.authuser):
            return HttpResponseForbidden('Cannot delete view "%s" for %s' % (v.name, self.urluser.username))

        v.delete()
        return HttpResponseRedirect(self.authuser.get_profile().get_view_url())
    

class ViewList(AtomFeed):
    def urlparams(self, kwargs):
        self.urluser = get_url_user(kwargs)
        
    def title(self, ns):
        return ns.span(ns.a('%s\'s' % self.urluser.username,
                            href=self.urluser.get_profile().get_absolute_url()),
                       ' views')
    
    def entries(self):
        return [ ViewEntry(v, proto=self) for v in View.objects.filter(owner=self.urluser) ]

    def render_json(self, *args, **kwargs):
        return self

    def jsonize(self):
        return self.entries()

    def _render_html(self, ns, *args, **kwargs):
        return ns.ul([ ns.li(e.render_summary(ns, *args, **kwargs))
                       for e in self.generate() ])    

    def do_POST(self, *args, **kwargs):
        if self.authuser != self.urluser:
            return HttpResponseForbidden('Cannot add view for %s' % self.urluser.username)

        try:
            name = self.request.POST['viewname'].strip().lower()
            description = self.request.POST.get('description', '').strip()
            search = self.request.POST['search']
            order = self.request.POST.get('order', '')
            limit = int(self.request.POST.get('limit', 100))
        except KeyError:
            return HttpResponseBadRequest('Missing field')
        except ValueError:
            return HttpResponseBadRequest('Malformed limit')

        if View.objects.filter(name=name).count() != 0:
            return HttpResponseConflict('View "%s" already exists' % name)

        v = View(name=name, description=description, search=search, order=order, limit=limit,
                 owner=self.urluser)
        v.save()
        return HttpResponseRedirect(v.get_absolute_url())        

view = ViewEntry()
viewsearch = ViewEntry()
viewlist = ViewList()

urlpatterns = patterns('',
                       ('^$',                           viewlist),
                       ('^(?P<viewname>[a-z0-9_-]+)/$', view),
                       ('^(?P<viewname>[a-z0-9_-]+)/-/(?P<search>.*)$', viewsearch),
                       )
