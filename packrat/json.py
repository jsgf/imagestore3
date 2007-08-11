from __future__ import absolute_import

import types

jsonizers = {}

def register_jsonize(type, func):
    jsonizers[type] = func

def extract_attr(obj, attrlist):
    ret = {}
    
    for a in attrlist:
        if hasattr(obj, a):
            ret[a] = getattr(obj, a)

    return ret
    
def write(obj):
    if type(obj) == types.GeneratorType:
        obj = list(obj)
        
    if hasattr(obj, 'jsonize'):
        obj = obj.jsonize()
    elif obj.__class__ in jsonizers:
        obj = jsonizers[obj.__class__](obj)
    
    if isinstance(obj, dict):
        return u'{%s}' % ','.join([ u'%s:%s' % (write(k), write(v))
                                   for (k,v) in obj.items() ])

    elif hasattr(obj, '__iter__'):
        return u'[%s]' % ','.join([ write(o) for o in obj ])

    elif obj is None:
        return u'null'

    elif isinstance(obj, bool):
        return obj and u'true' or u'false'
    
    elif isinstance(obj, str):
        return u'"%s"' % obj

    elif isinstance(obj, int) or isinstance(obj, long):
        return u'%d' % obj

    elif isinstance(obj, float):
        return u'%f' % obj

    else:
        raise Exception, 'Unencodable object %s, type=%s' % (obj, type(obj))

from datetime import date, time, datetime

register_jsonize(time, lambda dt: dt.isoformat())
register_jsonize(date, lambda dt: dt.isoformat())
register_jsonize(datetime, lambda dt: dt.isoformat())

from django.contrib.auth.models import User

register_jsonize(User, lambda u: { 'id': u.id, 'username': u.username })
