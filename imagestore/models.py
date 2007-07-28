from __future__ import absolute_import

from imagestore.picture import Picture, Comment
from imagestore.media import Media, MediaChunk
from imagestore.tag import Tag
from imagestore.camera import Camera, CameraTags
from imagestore.user import User, UserProfile

#Hack to deal with stale cache(?) issue
for c in [ Picture, Tag, Camera, CameraTags, User, UserProfile ]:
    try:
        del c._meta._all_related_many_to_many_objects
    except AttributeError:
        pass
