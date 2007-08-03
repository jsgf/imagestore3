from __future__ import absolute_import

import re
from fnmatch import fnmatch
import json
from cStringIO import StringIO
from datetime import datetime
from xml.etree.cElementTree import ElementTree

from django.http import HttpResponseNotAllowed, HttpResponse, HttpResponseNotFound
from django.views.decorators.cache import cache_control
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist

from imagestore.namespace import html

__all__ = [ 'RestBase', 'HttpResponseBadRequest', 'HttpResponseConflict',
            'HttpResponseContinue', ]

def serialize_xml(ret, file):
    ElementTree(ret).write(file, 'utf-8')
    file.write('\n')

def serialize_json(ret, file):
    file.write(json.write(ret))

def serialize_ident(ret, file):
    file.write(ret)

class RestBase(object):
    """ Useful base class for RESTful apps, which demultiplexes a
    request based on its HTTP method.  Also provides a simple
    implementation of HEAD based on GET; it need only be replaced if
    GET does way too much work to satisfy a HEAD request."""

    __slots__ = [ 'types', 'back_types', 'format', 'mimetype',
                  'request', 'args', 'kwargs', 'authuser' ]

    def __init__(self):
        self.authuser = None

        self.types = {}
        self.back_types = {}

        self.format = None
        self.mimetype = None
        
        for k,v,s in [ ('xml',          'application/xml',        serialize_xml),
                       ('html',         'text/html',              serialize_xml),
                       ('text',         'text/plain',             serialize_ident),
                       ('xhtml',        'application/xhtml+xml',  serialize_xml),
                       ('atom',         'application/atom+xml',   serialize_xml),
                       ('json',         'application/javascript', serialize_json),
                       ('binary',       'application/binary',     serialize_ident),
                       ]:
            self.add_type(k, v, s)

    def add_type(self, k, v, ser):
        #print 'adding type (%s, %s)' % (k,v)
        self.types[k] = (v, ser)
        if v not in self.back_types:
            self.back_types[v] = (k, ser)

    def get_Etag(self):
        return None

    def get_last_modified(self):
        return None

    def get_content_length(self):
        return None

    def get_doctype(self):
        return None

    def urlparams(self, kwargs):
        pass

    def match_accepts(self, formats, accepts):
        ok_types = [ k for (k,v) in self.back_types.items() if v[0] in formats ]
        print 'accepts=%s formats=%s, ok_types=%s' % (accepts, formats, ok_types)

        # match: 'text/plain;q=.5;ext=foo', and extract the type and q
        c = re.compile('([^;]*)(?:;(?:q=([0-9.]+)|[^;]*))*')

        best=(None, -1.)
        for a in accepts.split(','):
            m = c.match(a)
            if m is None:
                continue
            
            t,q = m.groups()

            if q is None:
                q = 1.

            q = float(q)

            for type in ok_types:
                print '  type=%s t=%s q=%f, best=%s' % (type, t, q, best)
                if fnmatch(type, t) and q > best[1]:
                    best = (type, q)

        ret = self.back_types.get(best[0], (None, None))[0]
        print 'returning best=%s -> %s' % (best[0], ret)
        return ret

    def render_error(self, *args, **kwargs):
        error = kwargs['error']
        body = kwargs.get('body', None)
        title = kwargs.get('title', 'Error %d' % error)
        
        resp = HttpResponse(mimetype='text/html')
        resp.status_code = error
            
        if body is not None:
            r = html.html(html.head(html.title(title)),
                          html.body(html.h1(title),
                                    body))
            serialize_xml(r, resp)

        return resp

    def not_acceptible(self, requested, formats):
        body = html.div(html.p('Couldn\'t find an appropriate format to match "%s" for resource. '
                               'Try one of these:' % requested),
                        html.ul([ html.li(html.a('%s: %s' % (fmt, self.types[fmt][0]),
                                                 href='?format=%s' % fmt))
                                  for fmt in formats ]))

        return self.render_error(error=406,
                                 title='Not Acceptible',
                                 body=body)

    def render(self, format=None, *args, **kwargs):
        """
        Generate the content for the current request.  Generally used
        for GET, but it may generate the body of a POST/PUT.  We
        determine the appropriate format for the content by either
        using an explicit format=X GET parameter, or from looking at
        the Accept: header and matching it against what we provide.

        Each format has a triplet associated with it:
        format - the short-form format name,
        mimetype - the full mime type,
        serializer - to convert the render format into something
                appropriate for the http body.
        """
        formats = [ f for f in self.types
                    if (hasattr(self, 'render_%s' % f) and
                        callable(getattr(self, 'render_%s' % f))) ]

        requested = None
        if format is None:
            # see if we've been told what format to use
            format = self.request.GET.get('format', None)
            requested = self.types.get(format, (None, None))[0]

        if format is None:
            accepts = self.request.META.get('HTTP_ACCEPT', None)
            requested = accepts
            if accepts:
                format = self.match_accepts(formats, accepts)

        if format is None or format not in formats:
            return self.not_acceptible(requested, formats)

        self.format = format
        self.mimetype = self.types[format][0]

        return (getattr(self, 'render_%s' % format))(self, *args, **kwargs)
    
    def do_GET(self, *args, **kwarg):
        return self.render()

    def do_HEAD(self, *args, **kwargs):
        resp = self.do_GET(self.request, *args, **kwargs)
        if resp.status_code == 200:
            resp.content = ''
            resp['Content-Length'] = '0'
            
        return resp

    @staticmethod
    def knobble(response):
        response.status_code = 304
        response.content = ''
        response['Content-Length'] = '0'

    def handle_cond_get(self, request, response):
        # Handle ETag
        et = self.get_Etag()
        if et is not None:
            et = '"%s"' % et
                
            ifnm = request.META.get('HTTP_IF_NONE_MATCH', None)
            if ifnm is not None:
                ifnm = re.split(', *', ifnm)
                if et in ifnm or '*' in ifnm:
                    self.knobble(response)
            response['ETag'] = et

        # Handle if-modified-since
        lm = self.get_last_modified()
        if lm is not None:
            last_mod = request.META.get('HTTP_IF_MODIFIED_SINCE', None)
            if last_mod is not None:
                last_mod = datetime.strptime(last_mod, '%a, %d %b %Y %H:%M:%S GMT')
                if last_mod > lm:
                    self.knobble(response)
            response['Last-Modified'] = lm.strftime('%a, %d %b %Y %H:%M:%S GMT')



    @cache_control(no_cache=True)
    def __call__(self, request, *args, **kwargs):
        """ Main entrypoint for all requests.  This allows the class
        instance to be called.  In turn, it examines the HTTP method,
        and farms the work off to an appropriate do_X method."""
        self.request = request
        self.args = args
        self.kwargs = kwargs

        if not hasattr(self, 'do_%s' % request.method):
            allowed = [ m.lstrip('do_') for m in dir(self) if m.startswith('do_') ]
            return HttpResponseNotAllowed(allowed)
        
        method = getattr(self, 'do_%s' % request.method)

        try:
            self.urlparams(kwargs)
        except ObjectDoesNotExist, e:
            return HttpResponseNotFound(e.message)
        
        ret = method(self, *args, **kwargs)

        if isinstance(ret, HttpResponse):
            response = ret
        else:
            response = HttpResponse(mimetype = self.mimetype)
            ser = self.types[self.format][1]
            if ser is not None:
                ser(ret, response)

        cl = self.get_content_length()
        if cl is not None and not response.has_header('Content-Length'):
            response['Content-Length'] = str(cl)

        if request.method in ('GET', 'HEAD'):
            self.handle_cond_get(request, response)

        now = datetime.utcnow()
        response['Date'] = now.strftime('%a, %d %b %Y %H:%M:%S GMT')

        #print 'type(content)=%s' % len(response.content)

        return response

class HttpResponseBadRequest(HttpResponse):
    def __init__(self, *args, **kwargs):
        HttpResponse.__init__(self, *args, **kwargs)
        self.status_code = 400

class HttpResponseConflict(HttpResponse):
    def __init__(self, *args, **kwargs):
        HttpResponse.__init__(self, *args, **kwargs)
        self.status_code = 409

class HttpResponseContinue(HttpResponse):
    def __init__(self, *args, **kwargs):
        HttpResponse.__init__(self, *args, **kwargs)
        self.status_code = 100

class HttpResponseExpectationFailed(HttpResponse):
    def __init__(self, *args, **kwargs):
        HttpResponse.__init__(self, *args, **kwargs)
        self.status_code = 417



class Test(RestBase):
    def __init__(self):
        super(Test,self).__init__()

    def render_text(self, *args, **kwargs):
        return 'Whoo\n'

    def render_html(self, *args, **kwargs):
        return html.h1('Hello, world!')

    def render_json(self, *args, **kwargs):
        return [ 'a list', 'of things' ]
    
test = Test()
