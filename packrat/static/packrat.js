// Wrap all packrat code
var packrat = function() {

    var sampler_elem_width = 100+4;

    // template for a thumbnail linked to a thickbox view
    this.thumb_template = function(img) {
	var th = img.sizes.stamp;
	var p = img.sizes.small;

	return $.SPAN({ Class: 'thumb' },
		      $.A({ href: p.url, Class: 'thickbox', rel: 'search-results', title: img.title },
			  $.IMG({ width: th.width, height: th.height,
					src: th.url, title: img.title })));
    };

    // simple ungrouped search results
    var image_search = function(el, search, params, render) {
	if (!(search instanceof Array ))
	    search = [ search ];

	if (params == null)
	    params = {};
	params.format = 'json';

	$(el).jsonupdate(packrat.searchbase + search.join('/') + '/',
			 params, render);
    };

    var sampler = function(el, search, number, render) {
	if (!render) {
	    render = function(el, data) {
		el.empty();

		for each (var img in data.results) {
		    el.append($.LI({ Class: 'image', id: 'img'+img.id },
				   this.thumb_template(img)));
		}
	    };
	}
	var ul = $.UL({ Class: 'horiz' });

	image_search(ul, [ 'vis:public', search ],
		     { limit: number, order: 'random' }, render);

	el = $(el)

	$(el).empty().append(ul);
    }

    return {
	image_search: image_search,
	sampler: sampler,
    }
}();

packrat.calendar = function () {
    var sortprops = function(o) {
	var a = new Array();

	for (var p in o)
	    a.push(p);

	return a.sort(function (a,b) { return a - b; });
	return a;
    }

    overview = function(el) {
	var get_counts = function(year) {
	    var count = 0;

	    for each (var m in year) {
		for each (var d in m) {
		    count += d.count;
		}
	    }

	    return count;
	};

	// This is a separate function so that it opens a new
	// scope for the event closures
	var make_yeardiv = function(data, year) {
	    var count = get_counts(data[year]);
	    var click, sampler, inner;
	    var id = 'year'+year;

	    var dom = $.DIV({ id: id, Class: 'year-overview' },
			    $.H2({}, click = $.A({href: '#'+id}, year),
				 ': '+count),
			    sampler = $.DIV({ Class: 'sampler', id: 'sampler_'+year}),
			    inner = $.DIV({Class: 'year'}, '...'));

	    inner = $(inner).hide();
	    sampler = $(sampler);
	    packrat.sampler(sampler, 'created:'+year, 8);

	    $(click).toggle(function () {
				sampler.disappear();
				yearview(inner, year, data[year]);
				return false;
			    },
			    function () {
				sampler.reveal();
				inner.disappear();
				packrat.sampler(sampler, 'created:'+year, 8);
				return false;
			    });

	    return dom;
	};

	var result_render = function(el, data) {
	    el.empty().hide();

	    for each (var year in sortprops(data)) {
		el.append(make_yeardiv(data, year));
	    }

	    el.show();
	};

	$(el).jsonupdate(packrat.searchbase, { format: 'calendar' }, result_render);
    };

    var yearview = function(el, year, months) {
	var get_counts = function(month) {
	    var count = 0;

	    for each (var d in month) {
		count += d.count;
	    }
	    return count;
	}

	var div = $($.DIV({Class: 'month-overview'}));
	for each (var m in sortprops(months)) {
	    (function (m) {
		var title, content, sampler;
		var id = 'month_'+year+'_'+m;

		div.append($.H3({ id: id },
				title = $.A({ href: "#"+id }, Date.monthNames[m-1]),
				': '+get_counts(months[m])));

		div.append(sampler = $.DIV({ Class: 'sampler' }));
		div.append(content = $.DIV({ Class: 'month' }));

		sampler = $(sampler);
		content = $(content);
		content.hide();

		var sampler_size = 7;

		packrat.sampler(sampler, 'created:'+year+'-'+m,
				sampler_size);

		$(title).toggle(function () {
				    sampler.disappear();
				    daysview(content, year, m, months[m]);
				    return false;
				},
				function () {
				    sampler.reveal();
				    content.disappear();
				    packrat.sampler(sampler,
						    'created:'+year+'-'+m,
						    sampler_size);
				    return false;
				});
	    })(m);
	}
	el.empty();
	el.append(div);
	el.reveal();
    }

    var daysview = function(el, year, month, days) {
	el = $(el);

	var d = new Date(year, month-1);

	var make_week = function() {
	    var w = new Array();
	    for (var d  = 0; d < 7; d++) 
		w.push($($.TD({})));
	    return w;
	};

	var cal = $($.TABLE({ Class: 'calendar-grid' }));
	var week = null;

	var dow = d.getFirstDayOfMonth();

	var add_week = function(cal, week) {
	    var row = $($.TR({}));
	    for each (var day in week)
	    row.append(day);
	    cal.append(row);
	};

	for (var i = 1; i <= d.getDaysInMonth(); i++, dow = (dow + 1) % 7) {
	    if (week == null || dow == 0) {
		if (week)
		    add_week(cal, week);

		week = make_week();
	    }

	    var dow_td = week[dow];

	    dow_td.append($.SPAN({ Class: 'number' }, i));
	    dow_td.addClass('day');
	    dow_td.addClass(Date.dayNames[dow]);

	    if (days[i] && days[i].count > 0) {
		dow_td.addClass('pictures');
		packrat.image_search(dow_td,
				     'created:'+year+'-'+month+'-'+i,
				     { order: 'random' },
				     function (el, data) {
					 el.css('background-image', 'url('+data.results[0].sizes.stamp.url+');');
				     });
	    }
	}

	add_week(cal, week);

	el.empty().append(cal);
	el.reveal();
    }

    return {
	overview: overview,
	yearview: yearview,
	monthview: null,
    };
}();

// Simple way to update an element with json:
// $(foo).jsonupdate(url, params, renderer...)
jQuery.fn.extend({
      jsonupdate: function(url, params, render) {
	    var el = this;
	    // embellishments: add "loading" spinning; error indication, etc...
	    jQuery.getIfModified(url, params, function (data) { render(el, data); }, 'json');
	},

    reveal: function() {
	    this.slideDown('slow');
	},

    disappear: function() {
	    this.slideUp('slow');
	}
    });

var displayCalendar = function(elem, year, month, day, period, search) {
	if (year == null) {
	    packrat.calendar.overview(elem);
	} else {
		if (month == null)
			calendarYearView(elem, year);
		else {
			if (day == null)
				calendarMonthView(elem, year, month);
			else
				calendarDayView(elem, year, month, day, period);
		}
	}
}
