from __future__ import absolute_import

from cStringIO import StringIO

from django.http import HttpRequest, HttpResponse

import ElementBuilder
from imagestore.RestBase import RestBase
from imagestore.namespace import atom, xhtml, opensearch

#content_type = 'application/xml'
content_type = 'application/atom+xml'

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

    def content_type(self):
        return content_type
    
    def render(self):
        entries = self.entries()

        feed = atom.feed(self.preamble(),
                         opensearch.totalResults('%d' % len(entries)),
                         atom.title(self.title()),
                         atom.subtitle(self.subtitle()),
                         atom.link({'ref': 'self', 'href': self.request.path}),
                         [ e.render() for e in entries ])

        return feed

class AtomEntry(RestBase):
    def __init__(self):
        RestBase.__init__(self)

    def content_type(self):
        return content_type

    def render(self):
        return atom.entry()

def atomtime(td):
    return td.strftime('%Y-%m-%dT%H:%M:%SZ')

def atomperson(self):
    return [ atom.name('%s %s' % (self.first_name, self.last_name)),
             atom.email(self.email),
             atom.username(self.username), 
             atom.id('urn:user:%d' % self.id) ]
