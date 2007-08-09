from __future__ import absolute_import

from ElementBuilder import Namespace

atom = Namespace('http://www.w3.org/2005/Atom', 'atom')
app = Namespace('http://www.w3.org/2007/app', 'app')

imst = Namespace('http://www.goop.org/packrat/schema/imagestore/', 'imst')
xhtml = Namespace('http://www.w3.org/1999/xhtml', 'xh')
opensearch = Namespace('http://a9.com/-/spec/opensearch/1.1/', 'os')
html = Namespace()                      # tag soup
timeline = Namespace()

__all__ = [ 'atom', 'imst', 'xhtml', 'html', 'opensearch' ]
