from __future__ import absolute_import

from datetime import datetime, date, time, timedelta
import calendar

__all__ = [ 'daterange' ]

def dateadd(d, year=0, month=0, day=0, week=0):
    y,m = d.year, d.month

    t = d.time()
    d = d.date()
    
    y += year
    m += month
    while m > 12:
        m -= 12
        y += 1
    while m < 1:
        m += 12
        y -= 1

    d = d.replace(year=y, month=m, day=min(calendar.monthrange(y, m)[1], d.day))

    d = date.fromordinal(d.toordinal() + day + week*7)

    return datetime.combine(d,t)

    
def weekstart(d):
    return datetime.fromordinal(d.toordinal() - calendar.weekday(d.year, d.month, d.day))

def roundup(period, dt):
    return rounddown(period, dateadd(dt, **{period: 1}) - timedelta(0,0,1))

def rounddown(period, dt):
    dt = dt.replace(hour=0, minute=0, second=0)
    
    if period == 'day':
        pass
    elif period == 'week':
        dt = weekstart(dt)
    elif period == 'month':
        dt = dt.replace(day=1)
    elif period == 'year':
        dt = dt.replace(month=1, day=1)

    return dt

class daterange(object):
    # start/end is None means unbounded
    __slots__ = [ 'start', 'end' ]

    @staticmethod
    def min(a,b):
        if a is None:
            return a

        if b is None:
            return b

        return min(a,b)

    @staticmethod
    def max(a,b):
        if a is None:
            return a

        if b is None:
            return b

        return max(a,b)

    def round(self, period):
        assert self.start is not None
        assert self.end is not None

        assert period in ('day', 'week', 'month', 'year')

        self.start = rounddown(period, self.start)
        self.end = roundup(period, self.end)

    def __init__(self, start=None, end=None, period=None):
        if start == 'today':
            start = date.today()
            if period is None:
                period = 'day'
        elif start == 'now':
            start = datetime.now()
            end = start

        if isinstance(start, date):
            start = datetime.combine(start, time(0,0))
        assert isinstance(start, datetime)

        if end is None:
            end = dateadd(start, day=1)
        elif end == 'today':
            end = date.today()
            if period is None:
                period = 'day'
        elif end == 'now':
            end = datetime.now()

        if isinstance(end, date):
            end = datetime.combine(end, time(0,0))
        assert isinstance(end, datetime)

        if end < start:
            start,end = end,start
            
        self.start = start
        self.end = end

        if period is not None:
            self.round(period)

    def dateadd(self, **kwargs):
        self.start = dateadd(self.start, **kwargs)
        if self.end is not None:
            self.end = dateadd(self.end, **kwargs)

    def __str__(self):
        return '%s - %s' % (self.start, self.end)

    def __or__(self, other):
        """ Union of two dateranges """
        start = daterange.min(self.start, other.start)
        end = daterange.max(self.end, other.end)

        return daterange(start, end)

    def __and__(self, other):
        """ Intersection of two dateranges """
        start = daterange.max(self.start, other.start)
        end = daterange.min(self.end, other.end)

        return daterange(start, end)
    
if __name__ == '__main__':
    dr2007=daterange(datetime(2007,1,1), datetime(2008,1,1))
    drjul2007 = daterange(datetime(2007,7,1),datetime(2007,8,1))
    dr2005=daterange(datetime(2005,1,1), datetime(2006,1,1))
    
    for t in [ dr2007,
               dr2005,
               drjul2007,
               dr2005 | drjul2007,
               dr2005 & drjul2007,
               dr2007 & drjul2007,
               dr2007 & (dr2005|drjul2007),
               daterange(start='now', period='week'),
               daterange(start='today', period='week'),
               daterange(start='today', period='day'),
               daterange(start=date(2007,12,31), period='week'),
               ]:
        print 'dr=%s' % t
