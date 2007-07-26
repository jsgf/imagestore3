from __future__ import absolute_import

import sha, md5
from datetime import datetime
import cStringIO as StringIO
import Image as PIL

import imagestore.EXIF as EXIF
import imagestore.camera
from imagestore.media import Media

sizes = {
    'thumb':    (100, 100),
    'tiny':     (320, 240),
    'small':    (640, 480),
    'medium':   (800, 600),
    'large':    (1024, 768),
    'full':     (10000, 10000)
    }

extensions = {
    'image/jpeg':               'jpg',
    'image/gif':                'gif',
    'image/tiff':               'tif',
    'image/vnd.nikon.nef':      'nef',
}

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

__all__ = [ 'importer' ]
