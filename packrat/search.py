from __future__ import absolute_import

import re

import datetime as dt

from django.db.models.query import Q, QNot

from .tag import Tag, tagre
from .daterange import daterange

__all__ = [ 'SearchParser' ]

tokens = []
tokre = None

def mktokre():
    regex = []
    idx = 0
    tokens = []
    
    for t in [ ('number',  r'\d+'),
               ('ident',   tagre),
               (':', ),
               ('/', ),
               (',', ),
               ('&', ),
               ('|', r'\|'),
               ('-', ),
               ('*', r'\*'),
               ('+', r'\+'),
               ('(', r'\('),
               (')', r'\)'),
               ('<=',r'\<='),
               ('<', r'\<'),
               ('=', ),
               ('>=', ),
               ('>', ),
               ('eof', '$') ]:
        name=t[0]
        pattern=name

        try:
            pattern = t[1]
        except IndexError:
            pass
        regex.append('(%s)' % pattern)
        idx += 1
        tokens.append(name)
    regex = ' *(?:%s)' % '|'.join(regex)
    #print 'regex=%s' % regex
    return (re.compile(regex, re.I | re.U), tokens)
    
tokre,tokens = mktokre()
del mktokre

def tokenize(str):
    idx = 0

    #print 'tokenizing (%s)' % str
    while idx <= len(str):
        m = tokre.match(str[idx:])
        if m is None:
            raise TokenException, 'Failed to match rest of "%s"' % str[idx:]

        idx += m.end()

        tid, = [ t[0] for t in enumerate(m.groups()) if t[1] is not None ]
        yield (tokens[tid], m.groups()[tid])

        if tokens[tid] == 'eof':
            break

def expect(want, tok, next):
    if tok[0] != want:
        raise ParseException('Expected tok "%s", got "%s:%s"' % (want, tok[0], tok[1]), next)
    v = tok[1]
    tok = next()
    return v,tok

def parse(query, tok, next):
    """
    Grammar:

    search := notExpr ('/' notExpr)*

    notExpr := '-'? orExpr

    orExpr := termExpr ('|' termExpr)*

    term := ident ':' predicate
         | number
         | ident
         | (':' ident)+ *?
         | '(' orExpr ')'

    predicate := daterel
              | ('public' | 'private' | 'restricted')
              | username

    daterel := ('<' | '<=' | '=' | '>=' | '>')? dateexpr

    periods := ('day' | 'week' | 'month' | 'year')
    
    dateexpr :=  periods ':' daterange
             | daterange

    daterange: datedelta ( ',' datedelta )?

    datedelta : datetime ( ('-' | '+') number? periods )*
              
    datetime := date ('T' time)?
             | '(' dateexpr ')'

    date := number ('-' number ('-' number)?)?
         | 'today'
         | 'now'
         
    time := number ':' number (':' number)

    """

    query, tok = parse_notExpr(query, tok, next)

    while tok[0] == '/':
        tok = next()
        query, tok = parse_notExpr(query, tok, next)

    return query

def parse_notExpr(query, tok, next):
    if tok[0] == '-':
        tok = next()
        if tok[0] == '/':
            # Ignore -/-/ sequences
            return query,tok
        
        q,tok = parse_orExpr(tok, next)
        if tok[0] == 'eof':
            return query,tok
        query = query.exclude(q)
    else:
        q, tok = parse_orExpr(tok, next)
        query = query.filter(q)

    return query,tok

def parse_orExpr(tok, next):
    q,tok = parse_term(tok, next)

    while tok[0] == '|':
        tok = next()
        tq, tok = parse_term(tok, next)
        q = q | tq

    return q,tok

def parse_term(tok, next):
    if tok[0] == '(':
        tok = next()
        q,tok = parse_orExpr(tok, next)
        v,tok = expect(')', tok, next)
        return q, tok
    
    elif tok[0] == 'number':
        q = Q(id = int(tok[1]))
        tok = next()
        return q, tok
    
    elif tok[0] == ':':
        tag = []
        while tok[0] == ':':
            tok = next()
            v,tok = expect('ident', tok, next)
            tag.append(v)

        tag = Tag.tag(':'.join(tag))
        if tok[0] == '*':
            tok = next()
            q = Q(tags__in = tag.more_specific())
        else:
            q = Q(tags = tag)
        return (q, tok)
    
    elif tok[0] == 'ident':
        t = tok[1]
        tok = next()
        if tok[0] == ':':
            tok = next()
            return parse_predicate(tok, next, t)
        else:
            return (Q(tags__word__iexact = t), tok)

    elif tok[0] == 'eof':
        return (Q(), tok)
    
    else:
        raise ParseException('unexpected token %s: %s' % tok, next)

def parse_predicate(tok, next, pred):
    from .picture import Picture
    
    if pred == 'vis':
        if tok[0] != 'ident' or tok[1] not in ('public', 'private', 'restricted'):
            raise ParseException('Unexpected visibility token %s:%s' % tok, next)
        q = Q(visibility = { 'public': Picture.PUBLIC,
                             'restricted': Picture.RESTRICTED,
                             'private': Picture.PRIVATE }[tok[1]])
        tok = next()
        return (q, tok)

    elif pred == 'owner':
        v,tok = expect('ident', tok, next)
        q = Q(owner__username = v)
        return (q,tok)

    elif pred == 'photog':
        v,tok = expect('ident', tok, next)
        q = Q(photographer__username = v)
        return (q,tok)

    elif pred == 'camera':
        v,tok = expect('ident', tok, next)
        q = Q(camera__nickname = v)
        return (q,tok)
    
    elif pred in ('created', 'updated', 'modified'):
        dr,tok,rel = parse_daterel(tok, next)
        assert isinstance(dr.start, dt.datetime)
        assert isinstance(dr.end, dt.datetime)
        
        if rel == '=':
            q = Q(**{'%s_time__range' % pred: (dr.start, dr.end)})
        elif rel == '<':
            q = Q(**{'%s_time__lt' % pred: dr.start})
        elif rel == '<=':
            q = Q(**{'%s_time__lt' % pred: dr.end})
        elif rel == '>=':
            q = Q(**{'%s_time__gte' % pred: dr.start})
        elif rel == '>':
            q = Q(**{'%s_time__gte' % pred: dr.end})
            
        return (q, tok)

    else:
        raise ParseException('unknown predicate: %s' % pred, next)

def parse_daterel(tok, next):
    rel = '='
    if tok[0] in ('<=', '<', '=', '>', '>='):
        rel = tok[0]
        tok = next()

    dr,tok = parse_dateexpr(tok, next)

    return dr,tok,rel

def is_period(tok):
    return tok[0] == 'ident' and tok[1] in ('day', 'week', 'month', 'year')
        
def parse_dateexpr(tok, next):
    period=None
    if is_period(tok):
        period = tok[1]
        tok = next()
        v,tok = expect(':', tok, next)
        
    ret,tok = parse_daterange(tok, next)

    if period is not None:
        ret.round(period)

    return ret, tok

def parse_daterange(tok, next):
    start,tok = parse_datedelta(tok, next)
    end = start
    
    if tok[0] == ',':
        tok = next()
        end,tok = parse_datedelta(tok, next)

    return (start | end), tok

def parse_datedelta(tok, next):
    dt, tok = parse_datetime(tok, next)

    # Getting a bit lexically swampy here: '-' is ambigious since it
    # could either be a continuation of a date, or the start of a
    # delta expression.  Date binds more tightly, and parens are
    # needed to disambiguate:
    #  (2007-6)-3month
    #  (2007-6-3)-month
    #
    # Similarly 'today-week' is tokenized as a single ident rather
    # than 'today' '-' 'week', so again, parens or a space are needed:
    # '(today)-week' 'today - week'

    while tok[0] in ('-', '+'):
        sign = tok[0]
        tok = next()
        
        n = 1
        
        if tok[0] == 'number':
            n = int(tok[1])
            tok = next()

        if sign == '-':
            n = -n
            
        if not is_period(tok):
            raise ParseException('expected day|week|month|year, got %s:%s' % tok, next)
        period = tok[1]
        tok = next()
        
        dt.dateadd(**{ period: n })

    return dt,tok

def parse_datetime(tok, next):
    if tok[0] == '(':
        tok = next()
        ret,tok = parse_dateexpr(tok, next)
        v,tok = expect(')', tok, next)
        return ret,tok
    
    if tok[0] == 'ident' and tok[1] in ('today', 'now'):
        dr = daterange(tok[1])
        tok = next()
        return (dr, tok)
    
    d,period,tok = parse_date(tok, next)

    t = dt.time(0,0,0)
    if tok[0] == 'ident' and tok[1] in ('T', 't'):
        tok = next()
        t,tok = parse_time(tok, next)

    return daterange(start=dt.datetime.combine(d,t), period=period), tok

def parse_date(tok, next):
    year = None
    month = 1
    day = 1

    v,tok = expect('number', tok, next)
    year = int(v)
    period = 'year'
    
    if tok[0] == '-':
        tok = next()
        v,tok = expect('number', tok, next)
        month = int(v)
        period = 'month'
        if tok[0] == '-':
            tok = next()
            v,tok = expect('number', tok, next)
            day = int(v)
            period = 'day'

    print 'period=%s' % period
    return (dt.date(year, month, day), period, tok)

def parse_time(tok, next):
    sec = 0

    v,tok = expect('number', tok, next)
    hour = int(v)

    v,tok = expect(':', tok, next)
    v,tok = expect('number', tok, next)
    min = int(v)

    if tok[0] == ':':
        tok = next()
        v,tok = expect('number', tok, next)
        sec = int(v)

    return dt.time(hour, min, sec), tok

class ParseException(Exception):
    def __init__(self, msg, next):
        remains = [ '%s:%s' % t for t in next.__self__ if t[0] != 'eof' ]

        msg = '%s: remaining tokens: %s' % (msg, remains)
        print 'msg=%s' % msg

        super(ParseException, self).__init__(msg)

class TokenException(ParseException):
    pass

class SearchParser(object):
    __slots__ = [ 'search', 'query' ]

    def __init__(self, search):
        self.search = search

    def parse(self, query):
        toks = tokenize(self.search)

        next = toks.next
        if 0:
            def trace():
                for t in toks:
                    print 'next: %s:%s' % t
                    yield t

            next = trace().next

        return parse(query, next(), next)
            
