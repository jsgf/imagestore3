from django.conf.urls.defaults import patterns, include
from django.shortcuts import render_to_response
from django.template import Context, loader

def index(request):
    return render_to_response('slideshow.html')

def calendar(request, *args, **kwargs):
    date = [ x for x in [ kwargs.get(k, None)
                          for k in ('year', 'month', 'day') ]
             if x is not None ]
    kwargs['date'] = '-'.join(date)
    if not kwargs['period']:
        kwargs['period'] = [ '', 'year', 'month', 'day' ] [ len(date) ]
    return render_to_response('calendar.html', kwargs)

urlpatterns = patterns('packrat.ui',
                       ('^$',            'index'),
                       (r'^calendar/'
                                r'(?:(?P<period>day|week|month|year)/)?'
                                r'(?:(?P<year>[0-9]{4})/'
                                        r'(?:(?P<month>[0-9]{1,2})/'
                                        r'(?:(?P<day>[0-9]{1,2})/)?)?)?'
                                r'(?:-/(?P<search>.+))?$',    'calendar'),
                       )
