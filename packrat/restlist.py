from __future__ import absolute_import

import sha

from .rest import RestBase
from .namespace import html, xhtml

class Entry(RestBase):
    def __init__(self, *args, **kwargs):
        super(Entry,self).__init__(*args, **kwargs)
        if hasattr(self, '_render_html'):
            self.__class__.render_html = Entry.__render_html
            self.__class__.render_xhtml = Entry.__render_xhtml
            
    def generate(self):
        """ Return a datastructure which can be rendered into any of the supported formats """
        None

    def render_json(self, *args, **kwargs):
        return self.generate()

    def links(self, ns):
        links = [ ns.link(type=self.types[fmt][0],
                          href=self.append_url_params('', {'format': fmt}),
                          rel="alternate")
                  for fmt in self.accepted_formats() ]
        return links

    def _html_frame(self, ns, inner):
        links = self.links(ns)

        title = self.title(ns)

        headtitle = title
        if hasattr(title, 'getiterator'):
            headtitle = ''
            headtitle = ''.join([ (e.text or '') + (e.tail or '') for e in title.getiterator() ])
                
        return ns.html(ns.head(links, ns.title(headtitle)),
                       ns.body(ns.h1(title), inner))

    def __render_html(self, *args, **kwargs):
        return self._html_frame(html, self._render_html(html, *args, **kwargs))

    def __render_xhtml(self, *args, **kwargs):
        return self._html_frame(xhtml, self._render_html(xhtml, *args, **kwargs))

class List(Entry):
    def entries(self):
        return []

    def generate(self):
        return self.entries()

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
        return None
    
    def _render_html(self, ns, *args, **kwargs):
        return ns.ul([ ns.li(e._render_html(ns, *args, **kwargs))
                       for e in self.generate() ])

    def render_json(self, *args, **kwargs):
        return ( e.render_json(*args, **kwargs) for e in self.generate() )

                          
