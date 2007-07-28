from django.conf.urls.defaults import patterns, include

# Order matters here, so that we get the reverse lookup correct
urlpatterns = patterns('',
            ('^image/', include('imagestore.picture')),
            ('^user/(?P<user>[^/]+)/', include('imagestore.user')),
            ('^(?P<urn>urn:[^/]*)/(?P<rest>.*)$', include('imagestore.urn')),
)
