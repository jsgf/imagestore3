from __future__ import absolute_import

from django.db import models

import string, re

tagroot = None

class Tag(models.Model):
    word = models.CharField(maxlength=50, db_index=True)
    scope = models.ForeignKey('self', db_index=True)

    # Tags may be geo-located
    #lat = models.FloatField(null=True)
    #long = models.FloatField(null=True)

    def __str__(self):
        return self.canonical()

    def depth(self):
        depth = 1
        if self.scope != tagroot:
            depth += self.scope.depth()
        return depth

    def canonical(self):
        ret = ':%s' % self.word
        if self.scope != tagroot:
            ret = self.scope.canonical() + ret
        return ret

    def is_more_specific(self, other):
        " Return true if this tag is more specific than other "

        tag = self
        while tag is not None:
            print 'tag=%s other=%s' % (tag, other)
            tag = tag.scope
            if tag == other:
                return True

        return False

    def more_specific(self):
        " Return list of all tags more specific than this one "
        expand = [ self ]
        ret = []

        while expand:
            ret.extend(expand)
            next = []
            for t in expand:
                next.extend(Tag.objects.filter(scope=t))
            expand = next

        return ret

    @staticmethod
    def tag(fulltag):
        assert tagroot is not None
        
        # canonicalize
        fulltag = string.strip(fulltag, u' :')

        tags = re.split(':+', fulltag)
        scope = tagroot
        for t in tags:
            tag, created = Tag.objects.get_or_create(scope=scope, word=t)
            scope = tag

        return scope
    
    class Meta:
        unique_together=(('scope', 'word'),)

def tagroot_setup():
    (root, created) = Tag.objects.get_or_create(word='')

    root.scope = root
    root.save()

    for t in Tag.objects.filter(scope__isnull=True):
        t.scope = root
        t.save()

    return root

tagroot = tagroot_setup()

__all__ = [ 'Tag' ]
