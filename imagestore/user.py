from __future__ import absolute_import

from django.conf.urls.defaults import patterns, include
from django.contrib.auth.models import User
from django.db import models
from django.db.models import permalink

from imagestore.atomfeed import AtomEntry
from imagestore.picture import PictureFeed
import imagestore.urn as urn
from imagestore.namespace import xhtml, atom

class UserProfile(models.Model):
    user = models.ForeignKey(User, unique=True, core=True,
                             edit_inline=models.STACKED)
    
    friends = models.ManyToManyField(User, core=True, related_name='friends')
    icon = models.ForeignKey('Picture', null=True)

    @permalink
    def get_absolute_url(self):
        return ('imagestore.views.user', (self.user.username,))

    def get_images_url(self):
        return self.get_absolute_url() + 'images/'
    
    def get_urn(self):
        return 'urn:user:%d' % self.id

class UserEntry(AtomEntry):
    def render(self):
        u = self.urluser
        up = u.get_profile()
        hcard = xhtml.div({'class': 'vcard'},
                          xhtml.a({'class': 'n', 'href': up.get_absolute_url() },
                                     xhtml.span({'class': 'given-name'}, u.first_name),
                                     ' ',
                                     xhtml.span({'class': 'family-name'}, u.last_name)),
                          ' (', xhtml.a({ 'href': u.get_absolute_url() },
                                        xhtml.span({'class': 'nickname'}, u.username)), ')',
                          xhtml.span({'class': 'email'}, u.email))

        if up.icon is not None:
            hcard += xhtml.img({'class': 'picture', 'src': up.icon.get_picture_url('icon')})
        
        return atom.entry(atom.content({'type': 'xhtml'}, hcard),
                          atom.link({'rel': 'images',
                                     'href': up.get_images_url()}),
                          [ atom.link({'rel': 'friend',
                                       'href': f.get_profile().get_absolute_url()})
                            for f in up.friends.all() ])
                                       
    def get_absolute_url(self):
        return self.urluser.get_profile().get_absolute_url()
    
urn.register('user',
             lambda urn: User.objects.get(id=int(urn[0])).get_profile())

urlpatterns = patterns('',
                       ('^$', 'imagestore.views.user'),
                       ('image/', include('imagestore.picture')),
                       )

__all__ = [ 'User', 'UserProfile', 'UserEntry' ]
