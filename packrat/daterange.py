from __future__ import absolute_import

from datetime import datetime, date, time, timedelta
import calendar

__all__ = [ 'daterange' ]

def dateadd(d, year=0, month=0, day=0, week=0):
    y,m = d.year, d.month

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

    return d
    
def weekstart(d):
    return datetime.fromordinal(d.toordinal() - calendar.weekday(d.year, d.month, d.day))


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

    def __init__(self, start=None, end=None, period=None):
        if start == 'today':
            start = date.today()
            if period is None and end is None:
                period = 'day'
        elif start == 'now':
            start = datetime.now()
            end = start

        if isinstance(start, date):
            start = datetime.combine(start, time(0,0))

        if end == 'today':
            end = date.today()
        elif end == 'now':
            end = datetime.now()

        if isinstance(end, date):
            end = datetime.combine(end, time(0,0))
            
        if period is not None:
            if start is None:
                raise Exception("Must specify date with period (start=%s period=%s)" % (start, period))

            if period not in ('day', 'week', 'month', 'year'):
                raise Exception("Bad period '%s'" % period)

            start = start.date()

            if period == 'year':
                start = start.replace(month=1,day=1)
                end = dateadd(start, year=1)
            elif period == 'month':
                start = start.replace(day=1)
                end = dateadd(start, month=1)
            elif period == 'day':
                end = dateadd(start, day=1)
            elif period == 'week':
                start = weekstart(start)
                end = dateadd(start, week=1)

            start = datetime.combine(start, time(0,0))
            end = datetime.combine(end, time(0,0))
            
        if (start is not None and
            end is not None and
            end < start):
            start, end = end, start
            
        self.start = start
        self.end = end

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
