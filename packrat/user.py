from __future__ import absolute_import

from django.conf.urls.defaults import patterns, include
from django.contrib.auth.models import User
from django.db import models
from django.db.models import permalink
from django.http import HttpResponseRedirect, HttpResponseForbidden
from django.contrib.auth import login, logout, authenticate

from . import restlist, microformat
from .namespace import xhtml
from .rest import serialize_xml
from .json import extract_attr, register_jsonize

register_jsonize(User, lambda u: extract_attr(u, [ 'id', 'username', 'last_name', 'first_name', 'email' ]))


def secure_path(request, path=None, protocol='https'):
    if path is None:
        path = request.get_full_path()

    protocol = 'http'                   # TESTING only

    return '%s://%s%s' % (protocol, request.META['HTTP_HOST'], path)

class UserProfile(models.Model):
    user = models.ForeignKey(User, unique=True, core=True, related_name='profile',
                             edit_inline=models.STACKED)
    
    friends = models.ManyToManyField(User, core=True, related_name='friends')

    # This seems to be causing a recursive import problem
    #icon = models.ForeignKey('Picture', null=True)
    icon = None

    def get_urn(self, request):
        return '%s://%s%s' % ('http', request.META['HTTP_HOST'],
                              self.get_absolute_url())
    
    @permalink
    def get_absolute_url(self):
        return ('packrat.user.user', (self.user.username,))

    def get_image_url(self):
        return self.get_absolute_url() + 'image/'

    def get_search_url(self, search):
        return self.get_image_url() + '-/%s' % search

    def get_view_url(self):
        return self.get_absolute_url() + 'view/'

    def get_camera_url(self):
        return self.get_absolute_url() + 'camera/'

def get_url_user(kwargs):
    id = kwargs.get('user', None)
    if id is None:
        return None

    return User.objects.get(username = id)

class UserList(restlist.List):
    def title(self, ns):
        return 'Users'

    def entries(self):
        return [ UserEntry(u, proto=self) for u in User.objects.filter(is_active=True) ]
    
    def render_json(self, *args, **kwargs):
        return [ u.render_json(*args, **kwargs)
                 for u in self.entries() ]
    
    def _render_html(self, ns, error=None, *args, **kwargs):
        ret = ns.div()
        
        if self.authuser is None:
            if error:
                ret.append(ns.p({'class': 'error'}, error))
                
            ret.append(ns.form({'action': secure_path(self.request), 'method': 'POST' },
                               ns.label('Username: ', ns.input(type='text', name='username')),
                               ns.label('Password: ', ns.input(type='password', name='password')),
                               ns.input(type='submit')))
        else:
            ret.append(ns.p('Logged in as ', ns.a({ 'href': self.authuser.get_profile().get_absolute_url() },
                                                  self.authuser.username)))
            ret.append(ns.form({'action': secure_path(self.request), 'method': 'POST' },
                               ns.input(type='hidden', name='logout', value='yes'),
                               ns.label('Logout: ', ns.input(type='submit'))))
            
        ret.append(ns.ul({ 'class': 'users' },
                         [ ns.li({ 'id': u.urluser.username },
                                 microformat.hcard(u.urluser, ns=ns))
                           for u in self.entries() ]))
        return ret

    @permalink
    def get_absolute_url(self):
        return ('packrat.user.userlist', (), {})
    
    def do_POST(self, *args, **kwargs):
        return do_loginout(self, self.request, *args, **kwargs)

def do_loginout(self, request, *args, **kwargs):
    resp = HttpResponseRedirect(self.get_absolute_url())

    if self.authuser and self.request.POST.get('logout'):
        logout(self.request)
    elif self.request.POST.get('username') and self.request.POST.get('password'):
        user = authenticate(username=self.request.POST.get('username'),
                            password=self.request.POST.get('password'))

        print 'authenticate: %s' % user

        self.authuser = None
        if user and user.is_authenticated():
            self.authuser = user

        if user is None or not user.is_active:
            resp = self.render(format='html', error='Login failed', *args, **kwargs)
            self.status_code = 403      # forbidden
        else:
            login(self.request, user)
            resp = HttpResponseRedirect(user.get_profile().get_absolute_url())

    return resp

class UserEntry(restlist.Entry):
    __slots__ = [ 'urluser' ]

    def __init__(self, user=None, *args, **kwargs):
        super(UserEntry, self).__init__(*args, **kwargs)

        if user is not None:
            self.urluser = user
            
    def urlparams(self, kwargs):
        self.urluser = get_url_user(kwargs)

    def title(self, ns):
        u = self.urluser
        return '%s %s' % (u.first_name, u.last_name)

    def do_POST(self, *args, **kwargs):
        return do_loginout(self, self.request, *args, **kwargs)

    def jsonize(self):
        u = self.urluser
        up = u.get_profile()

        ret = extract_attr(u, [ 'id', 'username', 'last_name', 'first_name', 'email' ])
        ret.update({'picture-count':    u.pictures.count(),
                    'urn':              up.get_urn(self.request),
                    'camera-url':       up.get_camera_url(),
                    'image-url':        up.get_image_url(),
                    'logged-in':        self.authuser == self.urluser,
                    'friends':          u.get_profile().friends.all() })

        return ret

    def generate(self):
        return self.jsonize()
    
    def _render_html(self, ns, error=None, *args, **kwargs):
        u = self.urluser
        up = u.get_profile()

        content = ns.div()

        content.append(microformat.hcard(u, ns))

        if self.authuser is None:
            if error:
                content.append(ns.p({'class': 'error'}, error))
                
            content.append(ns.form({'action': secure_path(self.request), 'method':'POST' },
                                   ns.input(type='hidden', name='username', value=self.urluser.username),
                                   ns.label('Login Password: ', ns.input(type='password', name='password')),
                                   ns.input(type='submit')))
        elif self.authuser == self.urluser:
            content.append(ns.form({'action': secure_path(self.request), 'method':'POST' },
                                   ns.input(type='hidden', name='logout', value='yes'),
                                   ns.label('Logout: ', ns.input(type='submit'))))
            
        detail = ns.dl()
        content.append(detail)
        
        if up.friends.count() > 0:
            detail.append(ns.dt('Friends'))
            detail.append(ns.dd(ns.ul({ 'class': 'friends' },
                                      [ ns.li({ 'class': 'friend' },
                                              microformat.hcard(f, ns))
                                        for f in up.friends.all() ])))
        if u.camera_set.count() > 0:
            detail.append(ns.dt(ns.a({'href': self.append_url_params(up.get_camera_url()) },
                                     'Cameras')))
            detail.append(ns.dd(ns.ul({ 'class': 'cameras' },
                                      [ ns.li({ 'class': 'camera' },
                                              ns.a({'href': self.append_url_params(c.get_absolute_url())},
                                                   c.nickname))
                                        for c in u.camera_set.all() ])))
            
        detail.append(ns.dt('pictures'))
        detail.append(ns.dd(ns.a({ 'href': self.append_url_params(up.get_image_url()) },
                                       str(u.pictures.count()))))
        detail.append(ns.dt(ns.a('tags', href='tag/')))
        
        return content

    def get_absolute_url(self):
        return self.urluser.get_profile().get_absolute_url()
    
userlist = UserList()
user = UserEntry()

urlpatterns = patterns('',
                       ('^$',                           userlist),
                       ('^(?P<user>[^/]+)/$',           user),
                       ('^(?P<user>[^/]+)/image/',      include('packrat.picture')),
                       ('^(?P<user>[^/]+)/camera/',     include('packrat.camera')),
                       ('^(?P<user>[^/]+)/view/',       include('packrat.view')),
                       ('^(?P<user>[^/]+)/tag/$',       'packrat.tag.usertaglist'),
                       ('^(?P<user>[^/]+)/tag/(?P<tagpart>[a-zA-Z0-9_ -]+)/$',       'packrat.tag.usertagcomplete'),
                       )

def setup():
    # Make sure everyone has a userprofile
    # XXX how to hook user creation?
    for u in User.objects.all():
        if u.profile.count() == 0:
            u.profile.create()

setup()

__all__ = [ 'UserProfile', 'UserEntry', 'get_url_user' ]
