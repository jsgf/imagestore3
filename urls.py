from django.conf.urls.defaults import *

urlpatterns = patterns('',
    # Example:
    # (r'^imagestore/', include('imagestore3.foo.urls')),

    # Uncomment this for admin:
     (r'^admin/', include('django.contrib.admin.urls')),

     (r'^imagestore/', include('imagestore.urls')),
)
