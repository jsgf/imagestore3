from __future__ import absolute_import

from django.http import HttpResponseNotAllowed, HttpResponseNotFound
from django.views.decorators.cache import cache_control
from django.contrib.auth.models import User

class RestBase(object):
    """ Useful base class for RESTful apps, which demultiplexes a
    request based on its HTTP method.  Also provides a simple
    implementation of HEAD based on GET; it need only be replaced if
    GET does way too much work to satisfy a HEAD request."""

    __slots__ = [ 'urluser', 'request', 'args', 'kwargs' ]
    
    def __init__(self):
        self.urluser = None

    def methods(self):
        return ['GET', 'HEAD' ]

    def not_allowed(self):
        return HttpResponseNotAllowed(self.methods())
    
    def do_GET(self):
        return self.not_allowed()

    def do_HEAD(self, *args, **kwargs):
        resp = self.do_GET(self.request, *args, **kwargs)
        if resp.status_code == 200:
            resp.body = None
        return resp

    def do_POST(self, *args, **kwargs):
        return self.not_allowed()

    def do_PUT(self, *args, **kwargs):
        return self.not_allowed()

    def do_DELETE(self, *args, **kwargs):
        return self.not_allowed()

    @cache_control(no_cache=True)
    def __call__(self, request, *args, **kwargs):
        self.request = request
        self.args = args
        self.kwargs = kwargs

        method = getattr(self, 'do_%s' % request.method)

        if 'user' in kwargs:
            try:
                self.urluser = User.objects.get(username=kwargs['user'])
            except User.DoesNotExist:
                return HttpResponseNotFound('User "%s" not found' % kwargs['user'])

        if 'picid' in kwargs:
            from imagestore.picture import Picture
            try:
                # XXX filter visibility
                self.picture = Picture.objects.get(pk=int(kwargs['picid']))
            except Picture.DoesNotExist:
                return HttpResponseNotFound('Picture %d not found' % kwargs['picid'])

        if 'camnick' in kwargs:
            from imagestore.camera import Camera
            try:
                self.camera = Camera.objects.get(nickname = kwargs['camnick'])
            except Camera.DoesNotExist:
                return HttpResponseNotFound('Camera %d not found' % kwargs['camnick'])
                
        return method(self, *args, **kwargs)

__all__ = [ 'RestBase' ]
