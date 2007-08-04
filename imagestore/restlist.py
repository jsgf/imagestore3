import json
import sha

from imagestore.rest import RestBase

from namespace import html, xhtml

class Entry(RestBase):
    def generate(self):
        """ Return a datastructure which can be rendered into any of the supported formats """
        yield

    def render_json(self, *args, **kwargs):
        return self.generate()

    def alt_links(self, ns):
        links = [ ns.link(type=self.types[fmt][0],
                          href=self.append_url_params('', {'format': fmt}),
                          rel="alternate")
                  for fmt in self.accepted_formats() ]
        return links

    def _html_frame(self, ns, inner):
        links = self.alt_links(ns)
        
        return ns.html(ns.head(links, ns.title(self.title())),
                       ns.body(ns.h1(self.title()), inner))

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

    def get_Etag(self):
        count=0
        sha1 = sha.new()
        for e in self.generate():
            et = e.get_Etag()
            if et is not None:
                count += 1
                sha1.update(et)

        if count > 0:
            return sha1.digest().encode('hex')

    def _render_html(self, ns, *args, **kwargs):
        return ns.ul([ ns.li(e._render_html(ns, *args, **kwargs))
                       for e in self.generate() ])

    def render_json(self, *args, **kwargs):
        # XXX use an incremental json encoder
        return [ e.generate() for e in self.generate() ]

                          
