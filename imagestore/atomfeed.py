from __future__ import absolute_import

from django.http import HttpRequest, HttpResponse

import ElementBuilder
from imagestore.rest import RestBase
from imagestore.namespace import atom, xhtml

#content_type = 'application/xml'
content_type = 'application/atom+xml'

class AtomFeed(RestBase):
    __slots__ = [ 'title', 'subtitle', 'uri' ]

    def __init__(self):
        super(AtomFeed, self).__init__()

    def title(self):
        return ''

    def subtitle(self):
        return ''
    
    def entries(self):
        return []

    def preamble(self):
        return []

    def content_type(self):
        return content_type

    def opensearch(self):
        return None
    
    def render(self):
        entries = self.entries()

        mod = self.get_last_modified()
        updated=[]
        if mod is not None:
            updated = atom.updated(atomtime(mod))

        feed = atom.feed(self.preamble(),
                         self.opensearch(),
                         atom.title(self.title()),
                         updated,
                         atom.subtitle(self.subtitle()),
                         atom.link({'ref': 'self', 'href': self.request.path}),
                         [ e.render() for e in entries ])

        return feed

class AtomEntry(RestBase):
    def __init__(self):
        super(AtomEntry, self).__init__()

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
