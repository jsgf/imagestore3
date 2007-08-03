from xml.etree.cElementTree import ElementTree

from django.conf.urls.defaults import patterns, include
from django.http import HttpResponse

from imagestore.namespace import xhtml
from imagestore.rest import RestBase

class Index(RestBase):
    def render(self):
        ret = xhtml.ul(xhtml.li(xhtml.a({'href': 'image/'}, 'Images')),
                       xhtml.li(xhtml.a({'href': 'user/'}, 'Users')),
                       xhtml.li(xhtml.a({'href': 'tag/'}, 'Tags')))

        return ret
    
    def urlparams(self, kwargs):
        pass

    def do_GET(self, *args, **kwargs):
        ret = HttpResponse(mimetype='application/xhtml+xml')

        ElementTree(self.render()).write(ret, 'utf-8');

        return ret


index = Index()

# Order matters here, so that we get the reverse lookup correct
urlpatterns = patterns('',
            ('^$',                      'imagestore.urls.index'),
            #('ui/',                    include('imagestore.ui')),
            ('^camera/$',               'imagestore.camera.cameralist'),
            ('^image/',                 include('imagestore.picture')),
            ('^user/',                  include('imagestore.user')),
            ('^(?P<urn>urn:[^/]*)/(?P<rest>.*)$', include('imagestore.urn')),
            ('^test/$',         'imagestore.rest.test'),
)
