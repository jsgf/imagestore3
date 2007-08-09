from django.conf.urls.defaults import include, patterns

urlpatterns = patterns('',
    (r'^static/(?P<path>.*)$', 'django.views.static.serve', {'document_root': '/home/jeremy/hg/imagestore3/static/'}),

     (r'^admin/', include('django.contrib.admin.urls')),

     (r'^packrat/', include('packrat.urls')),
)
