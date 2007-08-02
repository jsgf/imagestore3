from imagestore.rest import RestBase
from imagestore.namespace import xhtml

content_type = 'application/xhtml+xml'

class HtmlEntry(RestBase):
    __slots__ = []
    
    def __init__(self):
        RestBase.__init__(self)

    def content_type(self):
        return content_type

class HtmlList(RestBase):
    __slots__ = []
    
    def __init__(self):
        RestBase.__init__(self)

    def content_type(self):
        return content_type

    def entries(self):
        return []

    def render(self):
        return xhtml.ul([ xhtml.li(e) for e in self.entries() ])

__all__ = [ 'HtmlEntry', 'HtmlList' ]
