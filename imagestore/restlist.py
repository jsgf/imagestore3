import json

from imagestore.rest import RestBase

from namespace import html, xhtml

class Entry(RestBase):
    def generate(self):
        """ Return a datastructure which can be rendered into any of the supported formats """
        yield

    def render_json(self, *args, **kwargs):
        return self.generate()

    def _html_frame(self, ns, inner):
        return ns.html(ns.head(ns.title(self.title())),
                       ns.body(inner))
    
    def render_html(self, *args, **kwargs):
        return self._html_frame(html, self._render_html(html, *args, **kwargs))

    def render_xhtml(self, *args, **kwargs):
        return self._html_frame(xhtml, self._render_html(xhtml, *args, **kwargs))

class List(Entry):
    def entries(self):
        return []

    def generate(self):
        for e in self.entries():
            yield e

    def _render_html(self, ns, *args, **kwargs):
        return ns.ul([ ns.li(e._render_html(ns, *args, **kwargs))
                       for e in self.generate() ])

    def render_json(self, *args, **kwargs):
        # XXX use an incremental json encoder
        return [ e.generate() for e in self.generate() ]

                          
