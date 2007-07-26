from __future__ import absolute_import

import string

from django.conf.urls.defaults import patterns
from django.http import HttpResponseRedirect, HttpResponseNotFound
from django.core.exceptions import ObjectDoesNotExist

namespace={}

def register(ns, handler):
    namespace[ns] = handler

def lookup(urn):
    """ Given a urn, return an appropriate object reference, or None
    if nothing appropriate is found."""
    s = string.split(urn, ':')

    assert s[0] == 'urn'

    ret = None
    try:
        ret = namespace[s[1]](s[2:])
    except (KeyError, ObjectDoesNotExist):
        pass

    return ret

def urn_redirect(request, urn, rest, *args, **kwargs):
    """ Redirect a urn-in-url to an actual object URL, if it exists """
    thing = lookup(urn)

    if thing is None:
        ret = HttpResponseNotFound(content='urn "%s" not matched' % urn)
    else:
        ret = HttpResponseRedirect(thing.get_absolute_url() + rest)

    return ret

urlpatterns = patterns('', ('^$', urn_redirect),)
