
from django.db.models import permalink
from django.http import HttpResponse
from django.conf.urls.defaults import patterns, include

from .namespace import xhtml
from . import restlist

class Index(restlist.Entry):
    def _render_html(self, ns):
        return ns.ul(ns.li(ns.a({'href': self.append_url_params('image/')}, 'Images')),
                     ns.li(ns.a({'href': self.append_url_params('user/')}, 'Users')),
                     ns.li(ns.a({'href': self.append_url_params('tag/')}, 'Tags')))

    def title(self, ns):
        return 'PackRat'

@permalink
def base_url():
    return ('packrat.urls.index', (), {})

index = Index()

# Order matters here, so that we get the reverse lookup correct
urlpatterns = patterns('',
            ('^$',                      'packrat.urls.index'),
            #('ui/',                    include('packrat.ui')),
            ('^camera/$',               'packrat.camera.cameralist'),
            ('^image/',                 include('packrat.picture')),
            ('^user/',                  include('packrat.user')),
            ('^tag/',                   include('packrat.tag')),
#            ('^test/$',         'packrat.rest.test'),
)
