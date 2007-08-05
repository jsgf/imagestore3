from __future__ import absolute_import

from django.http import HttpRequest, HttpResponse

import ElementBuilder
from imagestore.rest import RestBase
from imagestore.namespace import atom, xhtml

from imagestore import restlist

class AtomFeed(restlist.List):
    __slots__ = [ 'title', 'subtitle', 'uri' ]

    def __init__(self):
        super(AtomFeed, self).__init__()

    def title(self, ns):
        return ''

    def subtitle(self):
        return ''
    
    def entries(self):
        return []

    def preamble(self, ns):
        return []

    def opensearch(self):
        return None
    
    def render_atom(self, *args, **kwargs):
        entries = self.entries()

        mod = self.get_last_modified()
        updated=[]
        if mod is not None:
            updated = atom.updated(atomtime(mod))

        feed = atom.feed(self.preamble(atom),
                         self.opensearch(),
                         atom.title(self.title(xhtml)),
                         updated,
                         atom.subtitle(self.subtitle()),
                         atom.link({'ref': 'self', 'href': self.request.path}),
                         [ e.render_atom() for e in entries ])

        return feed

class AtomEntry(restlist.Entry):
    def __init__(self):
        super(AtomEntry, self).__init__()

    def render_atom(self, *args, **kwargs):
        ret = atom.entry()

def atomtime(td):
    return td.strftime('%Y-%m-%dT%H:%M:%SZ')

def atomperson(self):
    return [ atom.name('%s %s' % (self.first_name, self.last_name)),
             atom.email(self.email),
             atom.username(self.username), 
             atom.id('%s' % self.get_profile().get_absolute_url()) ]
