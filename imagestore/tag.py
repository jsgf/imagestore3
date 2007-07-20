from django.db import models

import string, re

class Tag(models.Model):
    word = models.CharField(maxlength=50, db_index=True)
    scope = models.ForeignKey('self', null=True, db_index=True)

    # Tags may be geo-located
    #lat = models.FloatField(null=True)
    #long = models.FloatField(null=True)

    def __str__(self):
        return self.canonical()

    def depth(self):
        depth = 1
        if self.scope is not None:
            depth += self.scope.depth()
        return depth

    def canonical(self):
        ret = ':%s' % self.word
        if self.scope is not None:
            ret = self.scope.canonical() + ret
        return ret

    def is_more_specific(self, other):
        " Return true if this tag is more specifc than other "

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
        # canonicalize
        fulltag = string.strip(fulltag, ':')
        fulltag = re.sub(':+', ':', fulltag)

        tags = string.split(fulltag, ':')
        scope = None
        for t in tags:
            if scope is None:
                # "scope = NULL" doesn't do what you'd (I'd) expect
                tag, created = Tag.objects.get_or_create(scope__isnull=True, word=t)
            else:
                tag, created = Tag.objects.get_or_create(scope=scope, word=t)
            scope = tag

        return scope
    
    class Meta:
        unique_together=(('scope', 'word'),)

