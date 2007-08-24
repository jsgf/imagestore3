// Wrap all packrat code
var packrat = function() {

    var sampler_elem_width = 100+4;

    // template for a thumbnail linked to a thickbox view
    var thumb_template = function(img) {
	var th = img.sizes.stamp;
	var p = img.sizes.small;

	return $.SPAN({ Class: 'thumb' },
		      $.A({ href: p.url, Class: 'thickbox', rel: 'search-results', title: img.title },
			  $.IMG({ width: th.width, height: th.height,
					src: th.url, title: img.title })));
    };

    var search_date = function(year, month, day) {
	var search = '' + year;
	if (month) {
	    search += '-' + month;
	    if (day)
		search += '-' + day;
	}

	return search;
    }

    var image_search_url = function(search) {
	if (!(search instanceof Array ))
	    search = [ search ];

	return packrat.searchbase + search.join('/') + '/';
    };

    // simple ungrouped search results
    var image_search = function(el, search, params, render) {
	if (params == null)
	    params = {};

	params.format = 'json';

	$(el).jsonupdate(image_search_url(search), params, render);
    };

    var sampler = function(el, search, number, render) {
	if (!render) {
	    render = function(el, data) {
		el.empty();

		for (var idx in data.results) {
		    var img = data.results[idx];
		    el.append($.LI({ Class: 'image', id: 'img'+img.id },
				   thumb_template(img)));
		}

		tb_init($('.thickbox', this));
	    };
	}
	var ul = $.UL({ Class: 'horiz' });

	image_search(ul, [ 'vis:public', search ],
		     { limit: number, order: 'random' }, render);

	el = $(el)

	$(el).empty().append(ul);
    }

    return {
	search_date: search_date,
	image_search: image_search,
	image_search_url: image_search_url,
	sampler: sampler,
	thumb_template: thumb_template,
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

    var calendar_url = function(year, month, day) {
	var url = packrat.calendar_url;

	if (year) {
	    url += year + '/';
	    if (month) {
		url += month + '/';
		if (day)
		    url += day + '/';
	    }
	}

	return url;
    }

    var daybyday = function(el, year, month, day, search, start) {
	var result_render = function(el, data) {
	    // XXX set up nav links
	    var prevdate = null;
	    var ul;
	    var tags;
	    var tagset;

	    el.empty();

	    for (var idx in data.results) {
		var img = data.results[idx];
		var dt = img.created_time.split('T');
		var d = dt[0].split('-');
		var date = new Date(d[0], d[1], d[2]);

		if (!prevdate || d > prevdate) {
		    var div;

		    div = $.DIV({id: 'day'+dt[0], Class: 'date'},
				$.H2({},$.A({href: calendar_url(d[0])},d[0]),'-',
				     $.A({href: calendar_url(d[0],d[1])},d[1]),'-',
				     $.A({href: calendar_url(d[0],d[1],d[2])},d[2])),
				tags = $.UL({Class: 'tags horiz'}),
				ul = $.UL({Class: 'horiz'}));

		    tags = $(tags);
		    ul = $(ul);

		    el.append(div);
		    
		    tagset = {};

		    prevdate = d;
		}

		for (var tidx in img.tags) {
		    var tag = img.tags[tidx];

		    if (!tagset[tag.full]) {
			tagset[tag.full] = tag;
			tags.append($.LI({}, $.A({href: '-/' + tag.full}, tag.description || tag.full)));
		    }
		}

		ul.append($.LI({}, packrat.thumb_template(img)));
	    }

	    tb_init($('.thickbox', el));
	}

	if (!start)
	    start = 0;

	$(el).jsonupdate(packrat.image_search_url([ 'created:' +
						  packrat.search_date(year, month, day),
						  search ]),
			 { format: 'json', order: 'created',
				 start: start, limit: 500 },
			 result_render);	
    }

    var overview = function(el) {
	var get_counts = function(year) {
	    var count = 0;

	    for (var midx in year) {
		var m = year[midx];
		for (var didx in m) {
		    var d = m[didx];
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
	    var p = sortprops(data);

	    el.empty().hide();

	    for (var yearidx in p) {
		var year = p[yearidx];
		el.append(make_yeardiv(data, year));
	    }

	    el.show();
	};

	$(el).jsonupdate(packrat.searchbase, { format: 'calendar' }, result_render);
    };

    var yearview = function(el, year, months) {
	var get_counts = function(month) {
	    var count = 0;

	    for (var didx in month) {
		var d = month[didx];
		count += d.count;
	    }
	    return count;
	}

	var div = $($.DIV({Class: 'month-overview'}));
	var p = sortprops(months);
	for (var midx in p) {
	    var m = p[midx];
	    (function (m) {
		var title, content, sampler;
		var id = 'month_'+year+'_'+m;
		var mdiv = $($.DIV({ id: id }));

		mdiv.append($.H3({ },
				title = $.A({ href: "#"+id }, Date.monthNames[m-1]),
				': '+get_counts(months[m])));

		mdiv.append(sampler = $.DIV({ Class: 'sampler' }));
		mdiv.append(content = $.DIV({ Class: 'month' }));

		div.append(mdiv);

		sampler = $(sampler);
		content = $(content);
		content.hide();

		var sampler_size = 7;

		packrat.sampler(sampler, 'created:'+year+'-'+m,
				sampler_size);

		$(title).toggle(function () {
				    sampler.disappear();
				    monthview(content, year, m, months[m]);
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

    var generate_cal_grid = function (year, month, callback) {
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
	    for (var dayidx in week) {
		var day = week[dayidx];
		row.append(day);
	    }
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

	    if (callback)
		callback(dow_td, year, month, i);
	}

	add_week(cal, week);

	return cal;
    }	

    var monthview = function(el, year, month, days) {
	el = $(el);

	var set_thumb = function(el, y, m, d) {
	    if (!days[d] || !days[d].count)
		return;

	    el.addClass('pictures');
	    packrat.image_search(el,
				 'created:'+y+'-'+m+'-'+d,
				 { order: 'random', limit: 1 },
				 function (el, data) {
				     var img = data.results[0].sizes.stamp;

				     el.css('background-image', 'url('+img.url+');');
				 });
	    $('.number', el).wrap($.A({href: calendar_url(y, m, d)}));
	};

	var cal = generate_cal_grid(year, month, set_thumb);

	el.hide();
	el.empty().append(cal);
	el.reveal();
    }

    var year = function(el, year) {
	$(el).jsonupdate(packrat.image_search_url('created:'+year),
			 { format: 'calendar' },
			 function (el, data) {
			     yearview(el, year, data[year]);
			 });
    }

    return {
	overview: overview,

	year: year,
	daybyday: daybyday,
    };
}();

// Simple way to update an element with json:
// $(foo).jsonupdate(url, params, renderer...)
jQuery.fn.extend({
      jsonupdate: function(url, params, render) {
	    var el = this;
	    // embellishments: add "loading" spinning; error indication, etc...
	    jQuery.getIfModified(url, params, function (data) { render(el, data); }, 'json');
	    return this;
	},

    reveal: function() {
	    this.slideDown('slow');
	    return this;
	},

    disappear: function() {
	    this.slideUp('slow');
	    return this;
	}
    });

var displayCalendar = function(elem, year, month, day, period, search) {
    if (year == null) {
	packrat.calendar.overview(elem);
    } else {
	if (month == null)
	    packrat.calendar.year(elem, year);
	else
	    packrat.calendar.daybyday(elem, year, month, day, search);
    }
}
