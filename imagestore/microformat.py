from __future__ import absolute_import

from datetime import datetime

from imagestore.atomfeed import atomtime
from imagestore.namespace import xhtml
import imagestore.EXIF as EXIF

def html_datetime(dt):
    return xhtml.dfn({ 'class': 'dtbegin', 'title': atomtime(dt) }, str(dt))

def html_daterange(dr):
    return xhtml.span({ 'class': 'daterange' },
                      html_datetime(dr.start), ' - ', html_datetime(dr.end))

def exif(exif, ns=xhtml):
    """ Generate a simple xhtml microformat encoding for exif data """
    dl = ns.dl({'class': 'exif'})

    keys = exif.keys()
    keys.sort()

    for k in keys:
        v = exif[k]
        # skip unknown or long binary elements
        if (k == 'JPEGThumbnail' or
            EXIF.FIELD_TYPES[v.field_type][1] in ('B', 'U') or
            len(v.values) > 200):
            continue

        dl.append(ns.dt(ns.dfn({'title': '%s 0x%04x' % (k.split(' ')[0], v.tag),
                                'class': 'type-%s' % EXIF.FIELD_TYPES[v.field_type][1]},
                               k)))

        if isinstance(v.values, list) and len(v.values) > 1:
            val = ns.ol([ ns.li(str(val)) for val in v.values ])
        elif isinstance(v.printable, datetime):
            val = ns.dfn({ 'class': 'dtbegin', 'title': atomtime(v.printable)},
                         str(v.printable))
        else:
            val = str(v.printable)

        dl.append(ns.dd(val))

    return dl

def hcard(u, ns=xhtml):
    if u is None:
        return []
    
    up = u.get_profile()
    
    hcard = ns.div({'class': 'vcard'},
                   ns.a({'class': 'n', 'href': up.get_absolute_url() },
                        ns.span({'class': 'given-name'}, u.first_name),
                        ' ',
                        ns.span({'class': 'family-name'}, u.last_name)),
                   ' (', ns.a({ 'href': u.get_absolute_url() },
                              ns.span({'class': 'nickname'}, u.username)), ')',
                   '<', ns.a({ 'href': 'mailto:%s' % u.email},
                             ns.span({'class': 'email'}, u.email)), '>'
                   )

    if up.icon is not None:
        hcard += ns.img({'class': 'picture', 'src': up.icon.get_picture_url('icon')})

    return hcard
