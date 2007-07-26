from __future__ import absolute_import

from cStringIO import StringIO
from xml.etree.cElementTree import ElementTree

from django.http import HttpRequest, HttpResponse

import ElementBuilder
from imagestore.RestBase import RestBase
from imagestore.namespace import atom, xhtml, opensearch

class AtomFeed(RestBase):
    __slots__ = [ 'title', 'subtitle', 'uri' ]

    def __init__(self):
        RestBase.__init__(self)

    def title(self):
        return ''

    def subtitle(self):
        return ''
    
    def methods(self):
        return [ 'GET', 'HEAD', 'POST' ]
    
    def entries(self):
        return []

    def preamble(self):
        return []

    def render(self):
        entries = self.entries()

        feed = atom.feed(self.preamble(),
                         opensearch.totalResults('%d' % len(entries)),
                         atom.title(self.title()),
                         atom.subtitle(self.subtitle()),
                         atom.link({'ref': 'self', 'href': self.uri}),
                         [ e.render() for e in entries ])

        return feed
    
    def do_GET(self, *args, **kwarg):
        self.uri = self.request.path

        feed = self.render()

        out = StringIO()
        ElementTree(feed).write(out, 'utf-8')
        out.write('\n')
        
        return HttpResponse(out.getvalue(), 'application/atom+xml')

class AtomEntry(RestBase):
    def __init__(self):
        RestBase.__init__(self)

    def render(self):
        return atom.entry()

    def do_GET(self, *args, **kwarg):
        self.uri = self.request.path

        feed = self.render()

        out = StringIO()
        ElementTree(feed).write(out, 'utf-8')
        out.write('\n')
        
        return HttpResponse(out.getvalue(), 'application/atom+xml')

def atomtime(td):
    return td.strftime('%Y-%m-%dT%H-%M-%SZ')

def atomperson(self):
    return [ atom.name('%s %s' % (self.first_name, self.last_name)),
             atom.email(self.email),
             atom.username(self.username), 
             atom.id('urn:user:%d' % self.id) ]

class HttpResponseConflict(HttpResponse):
    def __init__(self, *args, **kwargs):
        HttpResponse.__init__(self, *args, **kwargs)
        self.status_code = 409
