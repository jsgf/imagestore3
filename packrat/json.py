from __future__ import absolute_import

import types

from django.utils.simplejson.encoder import JSONEncoder

__all__ = [ 'register_jsonize', 'write' ]

jsonizers = {}

def register_jsonize(type, func):
    jsonizers[type] = func

def extract_attr(obj, attrlist):
    ret = {}
    
    for a in attrlist:
        if hasattr(obj, a):
            ret[a] = getattr(obj, a)

    return ret

class Encoder(JSONEncoder):
    def default(self, o):
        if hasattr(o, 'jsonize'):
            o = o.jsonize()
        elif o.__class__ in jsonizers:
            o = jsonizers[o.__class__](o)
        elif hasattr(o, '__iter__'):
            o = list(o)
        else:
            o = super(Encoder,self).default(o)

        return o

def write(obj):
    return Encoder(ensure_ascii=False, indent=2).encode(obj)

def write_iter(obj):
    return Encoder(ensure_ascii=False, indent=2).iterencode(obj)

from datetime import date, time, datetime

register_jsonize(time, lambda dt: dt.isoformat())
register_jsonize(date, lambda dt: dt.isoformat())
register_jsonize(datetime, lambda dt: dt.isoformat())
