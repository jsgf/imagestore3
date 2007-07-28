from __future__ import absolute_import

import sha, md5
import os
import tempfile
from datetime import datetime
import cStringIO as StringIO
import Image as PIL

import imagestore.EXIF as EXIF
import imagestore.camera
from imagestore.media import Media

########################################
# Config - XXX use std config
#

# ImageMagick "convert"
convert='/usr/bin/convert'

# IJG jpegtran
jpegtran='/usr/bin/jpegtran'

jpeg_quality = 80

# Font
font = "/usr/share/fonts/bitstream-vera/Vera.ttf"
fontsize = 12

#
########################################

class Image(object):
    sizes = {
        'thumb':    (160, 160),
        'tiny':     (320, 240),
        'small':    (640, 480),
        'medium':   (800, 600),
        'large':    (1024, 768),
        'full':     (10000, 10000),
        'orig':     (10000, 10000),
        }

    def __init__(self, pic, size):
        self.pic = pic
        self.size = size

        assert size in Image.sizes

        self.extension = mimetypes[pic.mimetype][0]


class StillImage(Image):
    def __init__(self, pic, size):
        super(StillImage, self).__init__(pic, size)

    def dimensions(self):
        p = self.pic
        
        (w, h) = (p.width, p.height)

        # transpose width and height for 90deg rotate
        if p.orientation in (90, 270):
            (w, h) = (h, w)

        # scale size
        (sw, sh) = Image.sizes[self.size]

        # no scaling if original is smaller than output
        if w < sw and h < sw:
            return (w, h)

        fx = sw / float(w)
        fy = sh / float(h)

        if fx < fy:
            return (sw, int(h * fx))
        else:
            return (int(w * fy), sh)

    def generate(self):
        """ Generate an image with the appropriate processing,
            returning a (media, mimetype) tuple.  This will always
            regenerate the media, so the caller should check to see
            if something appropriate already exists. """

        p = self.pic

        # no processing
        if self.size == 'orig':
            return (p.media('orig'), p.mimetype)

        (w, h) = Image.sizes[self.size]
        short = self.size in ('thumb', 'tiny')	# short watermark

        args = []

        # Strip all Exif
        args.append('-strip')

        # Rotate first
        if p.orientation != 0:
            args.append('-rotate %d' % -p.orientation)

        # Then scale down
        if w < p.width or h < p.height:
            args.append('-size %(w)dx%(h)d -resize %(w)dx%(h)d' % { 'w': w, 'h': h })

        copyright = p.copyright

        if not copyright:
            copyright = '\xa9%s %s' % (p.created_time.strftime('%Y'),
                                       (p.photographer or p.owner).email)
            if not short:
                'Copyright '+copyright

        brand = 'Imagestore '
        fontsz = fontsize
        
        if short:
            brand = ''
            fontsz = fontsz * .75

        # watermark
        if self.size != 'thumb':
            args.append('-box "#00000070" -fill white '
                        '-pointsize %(size)d -font %(font)s -encoding Unicode '
                        '-draw "gravity SouthWest text 10,20 \\"%(brand)s#%(id)d %(copy)s\\"" '
                        '-quality %(qual)d' % {
                'font': font,
                'size': fontsz,
                'id': p.id,
                'qual': jpeg_quality,
                'copy': copyright,
                'brand': brand
                })

        tmp = tempfile.NamedTemporaryFile(mode='wb', suffix='.%s' % self.extension)
        for c in p.chunks('orig'):
            tmp.write(c)
        tmp.flush()

        cmd = '%s %s %s jpg:-' % (convert, ' '.join(args), tmp.name)
        #print 'cmd=%s' % cmd
        result = os.popen(cmd)

        data = ''.join(result)
        m = Media.store(p.mediakey(self.size), data, cache=True)

        return (m, 'image/jpg')
        
class RawStillImage(StillImage):
    def __init__(self, pic, size):
        super(RawStillImage, self).__init__(pic, size)

class VideoImage(Image):
    def __init__(self, pic, size):
        super(VideoStillImage, self).__init__(pic, size)


mimetypes = {
    'image/jpeg':               ('jpg', StillImage),
    'image/gif':                ('gif', StillImage),
    'image/tiff':               ('tif', StillImage),
    'image/vnd.nikon.nef':      ('nef', RawStillImage),
    }


def ImageProcessor(pic, size):
    if pic.mimetype not in mimetypes:
        return None

    return mimetypes[pic.mimetype][1](pic, size)
    
def sniff_mimetype(file):
    file.seek(0)
    try:
        img = PIL.open(file)
        return PIL.MIME[img.format]
    except IOError:
        return None

class ImportError(Exception):
    def __init__(self, msg):
        self.message = msg

importers = {}

def register_importer(mimetype, importer):
    importers[mimetype] = importer

def importer(file, **kwargs):
    mimetype = kwargs.get('mimetype')

    if mimetype is None or mimetype not in importers:
        mimetype = sniff_mimetype(file)
        if mimetype is None:
            mimetype = 'application/binary'  # ?

    if mimetype not in importers:
        raise ImportError("no importer for mime type '%s'" % mimetype)

    if 'mimetype' in kwargs:
        del kwargs['mimetype']

    file.seek(0)
    return importers[mimetype](file=file, mimetype=mimetype, **kwargs)

def still_image_importer(file, mimetype, owner, visibility, camera = None,
                         created_time = None, sha1hash=None, tags=None,
                         **kwargs):
    from .picture import Picture
    
    file.seek(0)
    exif = EXIF.process_file(file)
    file.seek(0)
    img = PIL.open(file)

    file.seek(0)
    data = file.read()

    md5hash = md5.new(data).digest().encode('hex')

    if sha1hash is None:
        sha1hash = sha.new(data).digest().encode('hex')

    width,height = img.size

    if camera is None:
        camera = imagestore.camera.get_camera(owner, exif)

    if created_time is None:
        created_time = datetime.now()
        
        for dt in (('EXIF DateTimeOriginal', 'EXIF SubSecTimeOriginal'),
                   ('EXIF DateTimeDigitized', 'EXIF SubSecTimeDigitized'),
                   ('Image DateTime', 'EXIF SubSecTime')):
            if dt[0] in exif:
                created_time = exif[dt[0]].printable
                if dt[1] in exif:
                    us = float('.%s' % exif[dt[1]].printable) * 1000000
                    created_time = created_time.replace(microsecond = int(us))

    orientation = 0
    if 'Image Orientation' in exif:
        try:
            orientation = { 1: 0, 3: 180, 6: 270, 8: 90, 9: 0 }[exif['Image Orientation'].values[0]]
        except KeyError:
            pass
    
    p = Picture(sha1hash = sha1hash,
                md5hash = md5hash,
                width=width, height=height,
                datasize = len(data),
                mimetype = mimetype,
                owner = owner,
                visibility = visibility,
                camera = camera,
                created_time = created_time,
                orientation = orientation,
                **kwargs)
    p.save()

    try:
        m = Media.store(p.mediakey('orig'), data, sha1hash)
    except Exception, e:
        p.delete()
        raise e

    if tags:
        p.addtags(tags)

    return p

PIL.init()                            # load all codecs
for t in [ v for v in PIL.MIME.values() if v.startswith('image/') ]:
    register_importer(t, still_image_importer)

__all__ = [ 'importer', 'ImageProcessor' ]
