from __future__ import absolute_import

from .picture import Picture, Comment
from .media import Media, MediaChunk
from .tag import Tag
from .camera import Camera, CameraTags
from .user import User, UserProfile

#Hack to deal with stale cache(?) issue
for c in [ Picture, Tag, Camera, CameraTags, User, UserProfile ]:
    try:
        del c._meta._all_related_many_to_many_objects
    except AttributeError:
        pass
