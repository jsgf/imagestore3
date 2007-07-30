from __future__ import absolute_import

import re
from datetime import datetime
from xml.etree.cElementTree import ElementTree

from django.http import HttpResponseNotAllowed, HttpResponse, HttpResponseNotFound
from django.views.decorators.cache import cache_control
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist

class RestBase(object):
    """ Useful base class for RESTful apps, which demultiplexes a
    request based on its HTTP method.  Also provides a simple
    implementation of HEAD based on GET; it need only be replaced if
    GET does way too much work to satisfy a HEAD request."""

    __slots__ = [ 'request', 'args', 'kwargs', 'authuser' ]
    
    def __init__(self):
        self.authuser = None

    def methods(self):
        return ['GET', 'HEAD' ]

    def not_allowed(self):
        return HttpResponseNotAllowed(self.methods())

    def get_Etag(self):
        return None

    def content_type(self):
        return 'text/plain'

    def get_last_modified(self):
        return None

    def get_content_length(self):
        return None
    
    def do_GET(self, *args, **kwarg):
        resp = HttpResponse(mimetype = self.content_type())

        resp.write('<?xml version="1.0" encoding="utf-8"?>\n')
        ElementTree(self.render()).write(resp, 'utf-8')
        resp.write('\n')
        
        return resp

    def do_HEAD(self, *args, **kwargs):
        resp = self.do_GET(self.request, *args, **kwargs)
        if resp.status_code == 200:
            resp.content = ''
            resp['Content-Length'] = '0'
            
        return resp

    def do_POST(self, *args, **kwargs):
        return self.not_allowed()

    def do_PUT(self, *args, **kwargs):
        return self.not_allowed()

    def do_DELETE(self, *args, **kwargs):
        return self.not_allowed()

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
        self.request = request
        self.args = args
        self.kwargs = kwargs

        method = getattr(self, 'do_%s' % request.method)

        try:
            self.urlparams(kwargs)
        except ObjectDoesNotExist, e:
            return HttpResponseNotFound(e.message)
        
        response = method(self, *args, **kwargs)

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


__all__ = [ 'RestBase', 'HttpResponseBadRequest', 'HttpResponseConflict',
            'HttpResponseContinue' ]

