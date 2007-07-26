from __future__ import absolute_import

from imagestore.picture import (PictureFeed, PictureEntry, PictureImage, PictureExif,
                                CommentFeed)
from imagestore.user import UserEntry

picture = PictureEntry()
pic_image = PictureImage()
comments = CommentFeed()
exif = PictureExif()

user = UserEntry()
