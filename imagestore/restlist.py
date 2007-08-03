import json

from imagestore.rest import RestBase

from namespace import html, xhtml

class Entry(RestBase):
    def generate(self):
        """ Return a datastructure which can be rendered into any of the supported formats """
        yield

    def render_json(self, *args, **kwargs):
        return self.generate()
    
    def render_html(self, *args, **kwargs):
        kwargs['ns'] = html
        return self._render_html(*args, **kwargs)

    def render_xhtml(self, *args, **kwargs):
        kwargs['ns'] = xhtml
        return self._render_html(*args, **kwargs)

class List(Entry):
    def entries(self):
        return []

    def generate(self):
        for e in self.entries():
            yield e

    def _render_html(self, *args, **kwargs):
        ns=kwargs['ns']
        return ns.ul([ ns.li(e._render_html(*args, **kwargs))
                       for e in self.generate() ])

    def render_json(self, *args, **kwargs):
        # XXX use an incremental json encoder
        return [ e.generate() for e in self.generate() ]

                          
