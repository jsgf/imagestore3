from __future__ import absolute_import

from xml.etree.cElementTree import ElementTree

from django.conf.urls.defaults import patterns, include
from django.contrib.auth.models import User
from django.db import models
from django.db.models import permalink
from django.http import HttpResponse

from imagestore import urn, restlist
from imagestore.namespace import xhtml
import imagestore.microformat as microformat

class UserProfile(models.Model):
    user = models.ForeignKey(User, unique=True, core=True,
                             edit_inline=models.STACKED)
    
    friends = models.ManyToManyField(User, core=True, related_name='friends')

    # This seems to be causing a recursive import problem
    #icon = models.ForeignKey('Picture', null=True)
    icon = None
    
    @permalink
    def get_absolute_url(self):
        return ('imagestore.user.user', (self.user.username,))

    def get_image_url(self):
        return self.get_absolute_url() + 'image/'

    def get_search_url(self, search):
        return self.get_image_url() + '-/%s' % search

    def get_camera_url(self):
        return self.get_absolute_url() + 'camera/'

    def get_urn(self):
        return 'urn:user:%d' % self.id

def get_url_user(kwargs):
    id = kwargs.get('user', None)
    if id is None:
        return None

    return User.objects.get(username = id)

class UserList(restlist.List):
    def title(self):
        return 'Users'

    def _render_html(self, ns):
        h = ns.ul({ 'class': 'users' },
                  [ ns.li(microformat.hcard(u, ns=ns)) for u in User.objects.all() ])
        return h
    
    def urlparams(self, kwargs):
        pass

    def get_absolute_url(self):
        return self.urluser.get_profile().get_absolute_url()

class UserEntry(restlist.Entry):
    __slots__ = [ 'urluser' ]

    def urlparams(self, kwargs):
        self.urluser = get_url_user(kwargs)

    def title(self):
        u = self.urluser
        return '%s %s' % (u.first_name, u.last_name)

    def _render_html(self, ns, *args, **kwargs):
        u = self.urluser
        up = u.get_profile()

        content = microformat.hcard(u)

        detail = ns.dl()
        content.append(detail)
        
        if up.friends.count() > 0:
            detail.append(ns.dt('Friends'))
            detail.append(ns.dd(ns.ul({ 'class': 'friends' },
                                            [ ns.li({ 'class': 'friend' },
                                                       microformat.hcard(f))
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
                                       str(u.owned_pics.count()))))

        return content

    def get_absolute_url(self):
        return self.urluser.get_profile().get_absolute_url()
    
urn.register('user',
             lambda urn: User.objects.get(id=int(urn[0])).get_profile())

userlist = UserList()
user = UserEntry()

urlpatterns = patterns('',
                       ('^$',                           userlist),
                       ('^(?P<user>[^/]+)/$',           user),
                       ('^(?P<user>[^/]+)/image/',      include('imagestore.picture')),
                       ('^(?P<user>[^/]+)/camera/',     include('imagestore.camera')),
                       )

def setup():
    # Make sure everyone has a userprofile
    # XXX how to hook user creation?
    for u in User.objects.all():
        if u.userprofile_set.count() == 0:
            u.userprofile_set.create()

setup()

__all__ = [ 'UserProfile', 'UserEntry', 'get_url_user' ]
