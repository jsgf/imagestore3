from __future__ import absolute_import

from xml.etree.cElementTree import ElementTree

from django.conf.urls.defaults import patterns, include
from django.contrib.auth.models import User
from django.db import models
from django.db.models import permalink
from django.http import HttpResponse

import imagestore.urn as urn
from imagestore.namespace import xhtml
import imagestore.microformat as microformat
from imagestore.htmllist import HtmlList, HtmlEntry

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

class UserList(HtmlList):
    def render(self):
        h = xhtml.ul({ 'class': 'users' },
                     [ xhtml.li(microformat.hcard(u)) for u in User.objects.all() ])
        return h
    
    def urlparams(self, kwargs):
        pass

    def get_absolute_url(self):
        return self.urluser.get_profile().get_absolute_url()

class UserEntry(HtmlEntry):
    __slots__ = [ 'urluser' ]

    def urlparams(self, kwargs):
        self.urluser = get_url_user(kwargs)

    def render(self):
        u = self.urluser
        up = u.get_profile()

        content = microformat.hcard(u)

        detail = xhtml.dl()
        content.append(detail)
        
        if up.friends.count() > 0:
            detail.append(xhtml.dt('Friends'))
            detail.append(xhtml.dd(xhtml.ul({ 'class': 'friends' },
                                            [ xhtml.li({ 'class': 'friend' },
                                                       microformat.hcard(f))
                                              for f in up.friends.all() ])))
        if u.camera_set.count() > 0:
            detail.append(xhtml.dt(xhtml.a({'href': up.get_camera_url() }, 'Cameras')))
            detail.append(xhtml.dd(xhtml.ul({ 'class': 'cameras' },
                                            [ xhtml.li({ 'class': 'camera' },
                                                       xhtml.a({'href': c.get_absolute_url()},
                                                               c.nickname))
                                              for c in u.camera_set.all() ])))

        detail.append(xhtml.dt('pictures'))
        detail.append(xhtml.dd(xhtml.a({ 'href': up.get_image_url() },
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
