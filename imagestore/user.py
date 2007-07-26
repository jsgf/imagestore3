from __future__ import absolute_import

from django.conf.urls.defaults import patterns, include
from django.contrib.auth.models import User
from django.db import models
from django.db.models import permalink

from imagestore.atomfeed import AtomEntry
from imagestore.picture import PictureFeed
import imagestore.urn as urn
from imagestore.namespace import xhtml, atom
import imagestore.microformat as microformat

class UserProfile(models.Model):
    user = models.ForeignKey(User, unique=True, core=True,
                             edit_inline=models.STACKED)
    
    friends = models.ManyToManyField(User, core=True, related_name='friends')
    icon = models.ForeignKey('Picture', null=True)

    @permalink
    def get_absolute_url(self):
        return ('imagestore.user.user', (self.user.username,))

    def get_images_url(self):
        return self.get_absolute_url() + 'images/'
    
    def get_urn(self):
        return 'urn:user:%d' % self.id

class UserEntry(AtomEntry):
    def render(self):
        u = self.urluser
        up = u.get_profile()
        hcard = microformat.hcard(u)

        return atom.entry(atom.content({'type': 'xhtml'}, xhtml.div(hcard)),
                          atom.link({'rel': 'images',
                                     'href': up.get_images_url()}),
                          [ atom.link({'rel': 'friend',
                                       'href': f.get_profile().get_absolute_url()})
                            for f in up.friends.all() ])
                                       
    def get_absolute_url(self):
        return self.urluser.get_profile().get_absolute_url()
    
urn.register('user',
             lambda urn: User.objects.get(id=int(urn[0])).get_profile())

user = UserEntry()

urlpatterns = patterns('',
                       ('^$',           user),
                       ('image/',       include('imagestore.picture')),
                       ('camera/',      include('imagestore.camera')),
                       )

def setup():
    # Make sure everyone has a userprofile
    # XXX how to hook user creation?
    for u in User.objects.all():
        if u.userprofile_set.count() == 0:
            u.userprofile_set.create()

setup()

__all__ = [ 'User', 'UserProfile', 'UserEntry' ]
