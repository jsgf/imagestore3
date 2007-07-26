from datetime import datetime

from imagestore.atomfeed import atomtime
from imagestore.namespace import xhtml
import imagestore.EXIF as EXIF

def exif(exif):
    """ Generate a simple xhtml microformat encoding for exif data """
    dl = xhtml.dl({'class': 'exif'})

    keys = exif.keys()
    keys.sort()

    for k in keys:
        v = exif[k]
        # skip unknown or long binary elements
        if (k == 'JPEGThumbnail' or
            EXIF.FIELD_TYPES[v.field_type][1] in ('B', 'U') or
            len(v.values) > 200):
            continue

        dl.append(xhtml.dt(xhtml.abbr({'title': '0x%04x' % v.tag,
                                       'class': 'type-%s' % EXIF.FIELD_TYPES[v.field_type][1]},
                                      k)))

        if isinstance(v.values, list) and len(v.values) > 1:
            val = xhtml.ol([ xhtml.li(str(val)) for val in v.values ])
        elif isinstance(v.printable, datetime):
            val = xhtml.abbr({ 'class': 'dtbegin', 'title': atomtime(v.printable)},
                             str(v.printable))
        else:
            val = str(v.printable)

        dl.append(xhtml.dd(val))

    return dl

def hcard(u):
    if u is None:
        return []
    
    up = u.get_profile()
    
    hcard = xhtml.div({'class': 'vcard'},
                      xhtml.a({'class': 'n', 'href': up.get_absolute_url() },
                              xhtml.span({'class': 'given-name'}, u.first_name),
                              ' ',
                              xhtml.span({'class': 'family-name'}, u.last_name)),
                      ' (', xhtml.a({ 'href': u.get_absolute_url() },
                                    xhtml.span({'class': 'nickname'}, u.username)), ')',
                      '<', xhtml.a({ 'href': 'mailto:%s' % u.email},
                                   xhtml.span({'class': 'email'}, u.email)), '>'
                      )

    if up.icon is not None:
        hcard += xhtml.img({'class': 'picture', 'src': up.icon.get_picture_url('icon')})

    return hcard
