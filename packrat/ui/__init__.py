from django.conf.urls.defaults import patterns, include
from django.shortcuts import render_to_response
from django.template import Context, loader

def index(request):
    return render_to_response('main.html')
    
urlpatterns = patterns('packrat.ui',
                       ('^$',            'index'),
                       )
