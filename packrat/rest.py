from __future__ import absolute_import

import re
from fnmatch import fnmatch
from cStringIO import StringIO
from datetime import datetime
import urllib

from django.http import HttpResponseNotAllowed, HttpResponse, HttpResponseNotFound
from django.views.decorators.cache import cache_control
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist

from ElementBuilder import ElementTree
from .namespace import html
from . import json

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

    __slots__ = [ 'types', 'back_types', 'format', 'default_formats', 'mimetype',
                  'request', 'args', 'kwargs', 'authuser', 'status_code' ]

    def __init__(self, proto=None):
        self.request = None
        self.authuser = None

        self.types = {}
        self.back_types = {}

        self.format = None
        self.mimetype = None

        self.default_formats = ('xhtml', 'html')

        if proto is not None:
            # If we're being created as a subordinate view to an
            # actual requested one, then copy some stuff across
            self.request = proto.request
            self.authuser = proto.authuser
            self.determine_format(proto.format)
        
        for k,v,s in [ ('xml',          'application/xml',        serialize_xml),
                       ('html',         'text/html',              serialize_xml),
                       ('text',         'text/plain',             serialize_ident),
                       ('xhtml',        'application/xhtml+xml',  serialize_xml),
                       ('atom',         'application/atom+xml',   serialize_xml),
                       # json should be application/json
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

    def match_accepts(self, accepts):
        ok_types = self.accepted_types()
        #print 'accepts=%s formats=%s, ok_types=%s' % (accepts, formats, ok_types)

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
                #print '  type=%s t=%s q=%f, best=%s' % (type, t, q, best)
                if fnmatch(type, t) and q > best[1]:
                    best = (type, q)

        ret = self.back_types.get(best[0], (None, None))[0]
        #print 'returning best=%s -> %s' % (best[0], ret)
        return ret

    def render_error(self, error, body, title=None, *args, **kwargs):
        if not title:
            title = 'Error %d' % error
        
        resp = HttpResponse(mimetype='text/html')
        resp.status_code = error
            
        if body is not None:
            r = html.html(html.head(html.title(title)),
                          html.body(html.h1(title),
                                    body))
            serialize_xml(r, resp)

        return resp

    def not_acceptible(self, requested):
        body = html.div(html.p('Couldn\'t find an appropriate format to match "%s" '
                               'for this resource. Try one of these:' % requested),
                        html.ul([ html.li(html.a({ 'type':self.types[fmt][0] },
                                                 '%s: %s' % (fmt, self.types[fmt][0]),
                                                 href=self.append_url_params('', { 'format': fmt })))
                                  for fmt in self.accepted_formats() ]))

        return self.render_error(error=406,
                                 title='Not Acceptible',
                                 body=body)

    def accepted_formats(self):
        return [ f for f in self.types
                 if (hasattr(self, 'render_%s' % f) and
                     callable(getattr(self, 'render_%s' % f))) ]

    def accepted_types(self):
        return [ k for (k,v) in self.back_types.items()
                 if v[0] in self.accepted_formats() ]

    def append_url_params(self, base, param=None, remove=None):
        if param is None:
            param={}

        for k in self.request.GET.keys():
            if k not in param:
                param[k] = self.request.GET[k]

        if remove:
            if isinstance(remove, str):
                remove = [remove]

            for r in remove:
                if r in param:
                    del param[r]

        #print 'param=%s -> %s' % (param, urllib.urlencode(param))
        if not param:
            return base
        
        return '%s?%s' % (base, urllib.urlencode(param))

    def determine_format(self, format=None):
        """
        We determine the appropriate format for the content by either
        using an explicit format=X GET parameter, or from looking at
        the Accept: header and matching it against what we provide.

        Each format has a triplet associated with it:
        format - the short-form format name,
        mimetype - the full mime type,
        serializer - to convert the render format into something
                appropriate for the http body.
        """
        formats = self.accepted_formats()

        requested = None
        if format is None:
            # see if we've been told what format to use
            format = self.request.GET.get('format', None)
            requested = self.types.get(format, (format, None))[0]

        if format is None:
            accepts = self.request.META.get('HTTP_ACCEPT', None)
            requested = accepts
            if accepts:
                format = self.match_accepts(accepts)

        if format is None or format not in formats:
            #print 'failed: trying one of %s' % (self.default_formats,)
            if self.default_formats:
                f = [ f for f in self.default_formats if f in formats ]
                if f:
                    format = f[0]

        if format is None or format not in formats:
            return self.not_acceptible(requested)

        self.format = format
        self.mimetype = self.types[format][0]        

    def render(self, format=None, *args, **kwargs):
        """
        Generate the content for the current request.  Generally used
        for GET, but it may generate the body of a POST/PUT.
        """
        return (getattr(self, 'render_%s' % self.format))(*args, **kwargs)
    
    def do_GET(self, *args, **kwargs):
        return self.render(*args, **kwargs)

    def do_HEAD(self, *args, **kwargs):
        resp = self.do_GET(self.request, *args, **kwargs)
        if not isinstance(resp, HttpResponse):
            resp = HttpResponse(mimetype=self.mimetype)
        if resp.status_code/100 == 2:
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
            et = '"%s %s"' % (self.format, et)
                
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

    def make_response(self, body):
        response = HttpResponse(mimetype = self.mimetype + '; charset=utf-8')
        response.status_code = self.status_code
        ser = self.types[self.format][1]
        ser(body, response)
        return response

    @cache_control(no_cache=True)
    def __call__(self, request, *args, **kwargs):
        """ Main entrypoint for all requests.  This allows the class
        instance to be called.  In turn, it examines the HTTP method,
        and farms the work off to an appropriate do_X method."""

        self.request = request
        self.args = args
        self.kwargs = kwargs

        self.authuser = None
        if request.user.is_authenticated():
            self.authuser = request.user
        
        if not hasattr(self, 'do_%s' % request.method):
            allowed = [ m.lstrip('do_') for m in dir(self) if m.startswith('do_') ]
            return HttpResponseNotAllowed(allowed)

        resp = self.determine_format()
        if resp:
            return resp
        
        method = getattr(self, 'do_%s' % request.method)

        try:
            resp = self.urlparams(kwargs)
            if resp is not None:
                return resp
        except ObjectDoesNotExist, e:
            return HttpResponseNotFound(e.message)

        self.status_code = 200
        ret = method(*args, **kwargs)

        if isinstance(ret, HttpResponse):
            response = ret
        else:
            response = self.make_response(ret)

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
