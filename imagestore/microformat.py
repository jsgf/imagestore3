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
            EXIF.FIELD_TYPES[v.field_type][1] in ('B') or 
            len(v.values) > 20):
            continue

        dl.append(xhtml.dt(xhtml.abbr({'title': '0x%x' % v.tag,
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
