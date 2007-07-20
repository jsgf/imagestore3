from django.conf.urls.defaults import patterns, include

from imagestore.picture import PictureFeed

urlpatterns = patterns('',
                       ('^user/(?P<user>[^/]+)/', include('imagestore.user')),
                       ('^image/', include('imagestore.picture')))
