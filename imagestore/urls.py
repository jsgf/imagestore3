
from django.db.models import permalink
from django.http import HttpResponse
from django.conf.urls.defaults import patterns, include

from imagestore.namespace import xhtml
from imagestore import restlist

class Index(restlist.Entry):
    def _render_html(self, ns):
        return ns.ul(ns.li(ns.a({'href': self.append_url_params('image/')}, 'Images')),
                     ns.li(ns.a({'href': self.append_url_params('user/')}, 'Users')),
                     ns.li(ns.a({'href': self.append_url_params('tag/')}, 'Tags')))

    def title(self, ns):
        return 'Imagestore'

@permalink
def base_url():
    return ('imagestore.urls.index', (), {})

index = Index()

# Order matters here, so that we get the reverse lookup correct
urlpatterns = patterns('',
            ('^$',                      'imagestore.urls.index'),
            #('ui/',                    include('imagestore.ui')),
            ('^camera/$',               'imagestore.camera.cameralist'),
            ('^image/',                 include('imagestore.picture')),
            ('^user/',                  include('imagestore.user')),
            ('^tag/',                   include('imagestore.tag')),
#            ('^(?P<urn>urn:[^/]*)/(?P<rest>.*)$', include('imagestore.urn')),
#            ('^test/$',         'imagestore.rest.test'),
)
