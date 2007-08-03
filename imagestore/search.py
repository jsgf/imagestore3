import re

from django.db.models.query import Q, QNot

from imagestore.tag import Tag

__all__ = [ 'SearchParser' ]

#
# Tokens
#
# Group "v" contains the interesting token value; even
#       valueless tokens have one for consistency
#
TOK_owner       = re.compile(r'owner:(?P<v>[a-z][a-z0-9_-]+)', re.I | re.U)
TOK_photog      = re.compile(r'photog:(?P<v>[a-z][a-z0-9_-]+)', re.I | re.U)
TOK_vis         = re.compile(r'vis:(?P<v>public|restricted|private)', re.I)
TOK_camera      = re.compile(r'camera:(?P<v>[a-z0-9 _-]+)', re.I)
TOK_reserved    = re.compile(r'(?P<v>[a-z]+):', re.I)

tagre           = '[a-z][a-z0-9_ -]*'
TOK_tag         = re.compile(r'(?P<v>%s)' % tagre, re.I | re.U)
TOK_qualtag     = re.compile(r'(?P<v>(?::%s)+:*\*?)' % tagre,
                             re.I | re.U)

# DATE := -?(YYYY-MM-DDTHH:MM:SS+TZ|(now|today))
datere          = r'''
(?:(?:\d{4}(?:-\d{1,2}(?:-\d{1,2}(?:T\d{1,2}:\d{1,2}(?::\d{1,2})?)?)?)?(?:\+(?:[+-])?\d{1,2})?)
| (?:today|now))
'''
# DATERANGE := DATE
#            | DATE,DATE
#            | (day|week|month|year)':'DATE
daterange_re       = r'''
(?:(?P<start>%(re)s),(?P<end>%(re)s))
|(?:(?P<date>%(re)s)
|(?:(?P<period>day|week|month|year):(?P<per_date>-?%(re)s)))
''' % { 're': datere }
# DATERELATION := (<|<=|=|>=|>)? DATERANGE
daterel         = r'(?:(?P<rel><|<=|=|>=|>|)%(dr)s)' % { 'dr': daterange_re }

#print daterel

TOK_created     = re.compile(r'(?P<op>created):(?P<v>%s)' % daterel, re.I | re.X)
TOK_modified    = re.compile(r'(?P<op>modified):(?P<v>%s)' % daterel, re.I | re.X)
TOK_uploaded    = re.compile(r'(?P<op>uploaded):(?P<v>%s)' % daterel, re.I | re.X)

TOK_id          = re.compile(r'(?P<v>\d+)')

TOK_sub         = re.compile(r'(?P<v>/+)')
TOK_and         = re.compile(r'(?P<v>[&+]+)')
TOK_or          = re.compile(r'(?P<v>\|)')
TOK_not         = re.compile(r'(?P<v>[-~])')
TOK_lp          = re.compile(r'(?P<v>\()')
TOK_rp          = re.compile(r'(?P<v>\))')
TOK_comma       = re.compile(r'(?P<v>,+)')

TOK_eof         = re.compile(r'(?P<v>)$')

# Order of tokens matters; need to put predicate: entries first
# so that tags don't get confused
tokens = [ TOK_owner, TOK_vis, TOK_camera, TOK_photog,
           TOK_created, TOK_modified, TOK_uploaded,
           TOK_reserved,
           TOK_tag, TOK_qualtag, TOK_id,
           TOK_sub, TOK_and, TOK_or, TOK_not,
           TOK_lp, TOK_rp, TOK_comma,
           TOK_eof ]

class SearchParser(object):
    __slots__ = [ 'search', 'query' ]
    
    def __init__(self, search):
        self.search = search
        self.query = self.parse()

    def parse(self):
        """
        Grammar for searches
        
        expr	: subExpr
                ;

        -- subsearches are separated by '/'; equivalent to & with
        -- weak precedence; can't be grouped with ()
        subExpr : catExpr ( '/' catExpr )*
                ;

        -- space-separated concatenated terms are anded together with
        -- weak precedence; can be grouped with ()
        catExpr : orExpr ( ','? orExpr )*
                ;

        -- Terms can be ORed together with |
        orExpr	: andExpr ( OR andExpr )*
                ;

        -- Strong precedence AND operator
        andExpr	: notExpr ( AND notExpr )*
                ;

        -- Tight-binding negation
        notExpr : ('-' | '~') term
                | term
                ;

        term	: '(' catExpr ')'       -- grouping
                | TAG                   -- match tag
                | QUALTAG               -- match qualified tag
                | ID                    -- match picture id
                | VIS                   -- match visibility
                | OWNER                 -- match owner
                | PHOTOG                -- match photographer
                | CAMERA                -- match camera
                ;

        ID      := '[0-9]+'
        SEP     := '/'+
        AND     := ('+' | '&')+
        OR      := '|'+

        OWNER   := 'owner:' user
        PHOTOG  := 'photog:' user
        CAMERA  := 'camera:' cameranick
        VIS     := 'vis:' ('public' | 'restricted' | 'private')

        TODO: time/date range
        
        Tags can take several forms:
                foo             simple tag
                foo bar         tag with spaces
                :foo:bar        qualified tag
                :foo:bar blat   qualified tag with spaces
        """

        # token lookahead
        lookahead=[]

        def tok_consume():
            " Consume a token from the input string "
            self.search = self.search.lstrip()
            for t in tokens:
                m = t.match(self.search)
                if m is not None:
                    self.search = self.search[m.end():]
                    return (t, m.group('v'), m.groupdict())

            raise TokenException('failed to match token with remains "%s"' % self.search)

        def tok_next(expect = None):
            " Return the next token "

            #print 'getting next tok from %s "%s"; expect %s' % (lookahead, self.search, expect)
            
            if lookahead:
                ret = lookahead.pop(0)
            else:
                ret = tok_consume()

            if expect is not None and expect is not ret[0]:
                raise ParserException('unexpected token: wanted %s, got %s', expect, ret[0])
            
            #print 'returning token %s %s' % ret

            return ret
        
        def tok_LA(x):
            " Return a lookahead token "
            while len(lookahead) < x:
                lookahead.append(tok_consume())

            ret = lookahead[x-1]
            #print 'LA(%s) returning %s "%s", remains:"%s"' % (x, ret[0], ret[1], self.search)
            return ret

        def parse_expr():
            return parse_subExpr()

        def parse_subExpr():
            q = parse_catExpr()

            while tok_LA(1)[0] is TOK_sub:
                tok_next(TOK_sub)
                q = q & parse_catExpr()

            return q

        def parse_catExpr():
            q = parse_orExpr()

            while tok_LA(1)[0] in (TOK_owner, TOK_vis, TOK_camera, TOK_photog,
                                   TOK_created, TOK_modified, TOK_uploaded,
                                   TOK_tag, TOK_qualtag, TOK_id, TOK_lp,
                                   TOK_comma):
                if tok_LA(1)[0] is TOK_comma:
                    tok_next(TOK_comma)
                q = q & parse_orExpr()

            return q

        def parse_orExpr():
            q = parse_andExpr()

            while tok_LA(1)[0] is TOK_or:
                tok_next(TOK_or)
                q = q | parse_andExpr()

            return q

        def parse_andExpr():
            q = parse_notExpr()

            while tok_LA(1)[0] is TOK_and:
                tok_next(TOK_and)
                q = q & parse_notExpr()

            return q

        def parse_notExpr():
            if tok_LA(1)[0] is TOK_not:
                tok_next(TOK_not)
                q = QNot(parse_term())
            else:
                q = parse_term()
            return q

        def parse_term():
            tok,val,match = tok_LA(1)

            if tok is TOK_lp:
                tok_next(TOK_lp)
                q = parse_catExpr()
                tok_next(TOK_rp)

            elif tok is TOK_owner:
                tok_next(tok)
                q = Q(owner__username = val)

            elif tok is TOK_photog:
                tok_next(tok)
                q = Q(photographer__username = val)

            elif tok is TOK_vis:
                tok_next(tok)
                val = val.lower()
                q = Q(visibility = { 'public': Picture.PUBLIC,
                                     'restricted': Picture.RESTRICTED,
                                     'private': Picture.PRIVATE }[val])

            elif tok is TOK_camera:
                tok_next(tok)
                q = Q(camera__nickname = val)

            # XXX TODO: search camera tags too
            # q = q | Q(camera__cameratags__tags__word = 'foo')
            # .extra(where=['imagestore_picture.created_time BETWEEN imagestore_picture__camera__cameratags.start AND imagestore_picture__camera__cameratags.end'])
            elif tok is TOK_tag:
                tok_next(tok)
                q = Q(tags__word = val)

            elif tok is TOK_qualtag:
                tok_next(tok)
                
                if val[-1] == '*':
                    val = val[:-1]
                    q = Q(tags__in = Tag.tag(val).more_specific())
                else:
                    q = Q(tags = Tag.tag(val))

            elif tok is TOK_id:
                tok_next(tok)
                q = Q(id = int(val))

            elif tok in (TOK_created, TOK_modified, TOK_uploaded):
                tok_next(tok)
                q = handle_datetime(match)

            elif tok is TOK_eof:
                tok_next(tok)
                q = Q()

            elif tok is TOK_reserved:
                raise ParserException('reserved predicate "%s" used: '
                                'did you mean to use a :qualified:tag?' % val)

            else:
                print 'tok=%s lp=%s rp=%s' % (tok, TOK_lp, TOK_rp)
                raise ParserException('unexpected token "%s" (%s), next %s, search=\"%s\"' % (tok, val, tok_LA(1)[0], self.search))

            return q

        def handle_datetime(groups):
            def parse_date(d):
                pieces = [ ('%Y', 'year'), ('-%m', 'month'), ('-%d', 'day'),
                           ('T%H:%M', None), (':%S', None) ]
                if d in ('today', 'now'):
                    return daterange(d)
                if d is None:
                    return None
                
                ret = None
                fmt = ''

                for p, period in pieces:
                    fmt += p
                    try:
                        time=dt.datetime.strptime(d, fmt)
                        if period is not None:
                            return daterange(time, period=period)
                        else:
                            return daterange(time, time)
                    except ValueError:
                        continue

                print 'failed to parse "%s"' % d
                return None
            
            print 'groups=%s' % (groups)

            start = parse_date(groups.get('start'))
            end = parse_date(groups.get('end'))
            date = parse_date(groups.get('date'))
            period = groups.get('period')
            per_date = parse_date(groups.get('per_date'))

            dr = None
            if start and end:
                dr = daterange(start.start, end.start)
            elif date:
                dr = date
            elif per_date and period:
                dr = daterange(start=per_date.start, period=period)

            if dr is None:
                return Q()      # bad date range?

            print 'daterange=%s' % dr
            
            field = '%s_time' % groups.get('op')
            arg = (dr.start, dr.end)
            cmp = 'range'
            
            rel = groups.get('rel')
            if rel == '<':
                arg = dr.start
                cmp = 'lt'
            elif rel == '<=':
                arg = dr.end
                cmp = 'lt'
            elif rel == '>':
                arg = dr.end
                cmp = 'gte'
            elif rel == '>=':
                arg = dr.start
                cmp = 'gte'
                
            return Q(**{'%s__%s'%(field, cmp): arg})
        
        return parse_expr()
