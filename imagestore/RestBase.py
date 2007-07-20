from django.http import HttpResponseNotAllowed, HttpResponseNotFound
from django.views.decorators.cache import cache_control
from django.contrib.auth.models import User

class RestBase(object):
    """ Useful base class for RESTful apps, which demultiplexes a
    request based on its HTTP method.  Also provides a simple
    implementation of HEAD based on GET; it need only be replaced if
    GET does way too much work to satisfy a HEAD request."""

    __slots__ = [ 'user', 'request', 'args', 'kwargs' ]
    
    def __init__(self):
        self.user = None

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
                self.user = User.objects.get(username=kwargs['user'])
            except User.DoesNotExist:
                return HttpResponseNotFound('User"%s" not found' % kwargs['user'])
        return method(self, *args, **kwargs)
