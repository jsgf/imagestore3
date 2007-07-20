from django.conf.urls.defaults import patterns, include
from django.contrib.auth.models import User
from django.db import models

from imagestore.atomfeed import atom
from imagestore.picture import PictureFeed

class UserProfile(models.Model):
    user = models.ForeignKey(User, unique=True, core=True, edit_inline=models.STACKED)
    
    friends = models.ManyToManyField(User, core=True, related_name='friends')
    icon = models.ForeignKey('Picture', null=True)

urlpatterns = patterns('',
                       ('image/', include('imagestore.picture')),
                       )
