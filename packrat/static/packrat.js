// Accordion
// - an element with class acc-control causes opening/closing
// - multiple acc-body classed pieces get alternated between

accordion = function(outer, useropt) {
    var options = {
	always_one: true,
	start_displayed: true,
    };

    $.extend(options, useropt);

    outer = $(outer);

    outer.addClass('accordion');
    
    // find non-nested accordion elements
    var find = function(match, scope) {
	return $(match, scope).not($('.accordion '+match, scope));
    }

    find('.acc-body', outer).hide();
    if (options.start_displayed)
	find('.acc-body:first', outer).show();

    find('.acc-control', outer).click(
	function () {
	    var cur = find('.acc-body:visible', outer);
	    var next = cur.next('.acc-body:hidden', outer);

	    if ((options.always_one || cur.size() == 0) && next.size() == 0)
		next = find('.acc-body:hidden', outer).filter(':first');

	    cur.disappear();
	    if (next.size()) {
		// search pattern excludes context node itself?
		if (next.is('.updateable'))
		    next.update();
		    
		find('.updateable', next).update();
		next.reveal();
		outer.removeClass('acc-hidden');
	    }
	    else
		outer.addClass('acc-hidden');

	    return false;
	});
};

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

		tb_init('.thickbox');
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

    var parsedate = function(datestr) {
	var dt = datestr.split('T');
	var d = dt[0].split('-');
	var t = dt[1].split(':');

	return new Date(d[0], d[1]-1, d[2], t[0], t[1], t[2]);
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
		var date = parsedate(img.created_time);
		var time = date.clone();

		date.clearTime();

		if (!prevdate || date > prevdate) {
		    var div;
		    var y = date.getFullYear();
		    var m = date.getMonth() + 1;
		    var d = date.getDate();
		    var ymd = y + '-' + m + '-' + d;

		    div = $.DIV({id: 'day_'+ymd, Class: 'date'},
				$.H2({},
				     $.A({href: '#', Class: 'acc-control' }, '+-'),
				     $.A({href: calendar_url(y)},y),'-',
				     $.A({href: calendar_url(y,m)},m),'-',
				     $.A({href: calendar_url(y,m,d)},d)),
				tags = $.UL({Class: 'tags horiz'}),
				ul = $.UL({Class: 'horiz acc-body'}));

		    tags = $(tags);
		    ul = $(ul);

		    accordion(div, { always_one: false });

		    el.append(div);
		    
		    tagset = {};

		    prevdate = date;
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

	    tb_init('.thickbox');
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
			    $.H2({}, $.A({href: '#'+id, Class: 'acc-control' }, year),
				 ': '+count),
			    sampler = $.DIV({ Class: 'sampler acc-body',
						    id: 'sampler_'+year}),
			    inner = $.DIV({Class: 'year acc-body'}, '...'));

	    packrat.sampler(sampler, 'created:'+year, 7);
	    $(inner).update(function () { yearview(this, year, data[year]); });

	    accordion(dom);

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
		var content, sampler;
		var id = 'month_'+year+'_'+m;
		var mdiv = $($.DIV({ id: id }));

		mdiv.append($.H3({ },
				 $.A({ href: "#"+id, Class: 'acc-control' },
				    Date.monthNames[m-1]),
				 ': ',
				 $.A({ href: calendar_url(year, m) },
				     get_counts(months[m]))));

		mdiv.append(sampler = $.DIV({ Class: 'sampler acc-body' }));
		mdiv.append(content = $.DIV({ Class: 'month acc-body' }));

		accordion(mdiv);

		div.append(mdiv);

		packrat.sampler(sampler, 'created:'+year+'-'+m,
				7);
		$(content).update(function () {
				      monthview(this, year, m, months[m]);
				  });
	    })(m);
	}
	el = $(el);
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
	    dow_td.addClass(Date.dayNames[dow].toLowerCase());

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

	calendar_url: calendar_url,
    };
}();

packrat.sidebar = function () {
    // Add a menu, which is basically an array of objects
    var menu = function (elem, menulist) {
	var ul = $('>ul', elem);
	if (ul.size() == 0) {
	    ul = $($.UL());
	    $(elem).append(ul);
	}

	ul.empty();

	for (var mi in menulist) {
	    var entry = menulist[mi];
	    var attr = {};
	    var url = '#';
	    var item;

	    if (entry.attr)
		attr = entry.attr;
	    if (entry.url)
		url = entry.url;

	    var e = $.LI(attr, item = $.SPAN({}, $.A({ href: url }, entry.item)));

	    if (entry.selected)
		$(e).addClass('selected');

	    if (entry.id)
		$(e).attr('id', entry.id);

	    ul.append(e);

	    if (entry.sub) {
		var s = menu(e, entry.sub);

		if (entry.collapse) {
		    $(s).addClass('acc-body');
		    $(item).append($.A({ href: '#', Class: 'acc-control' }, '+-'));
		    accordion(e, { always_one: false,
				   start_displayed: entry.visible });
		}
	    }
	}

	return ul;
    };

    return {
	menu: menu,
    };
}();

// Simple way to update an element with json:
// $(foo).jsonupdate(url, params, renderer...)
jQuery.fn.extend({
      update: function(fn) {
	    if (typeof fn == 'undefined')
		this.trigger('update');
	    else {
		this.bind('update', fn);
		this.addClass('updateable');
	    }
	},

      jsonupdate: function(url, params, render) {
	    var el = this;

	    var do_update = function () {
		// embellishments: add "loading" spinning; error indication, etc...
		jQuery.getIfModified(url, params, function (data) { render(el, data); }, 'json');
		return false;
	    }

	    this.update(do_update);

	    do_update();

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

    $('#sb-calendar').jsonupdate(packrat.image_search_url(),
				 { format: 'calendar' },
				 function (el, data) {
				     var menu = [];

				     for (var y in data) {
					 var monthmenu = [];

					 for (var m in data[y]) {
					     monthmenu.push({ item: Date.monthNames[m-1],
								url: packrat.calendar.calendar_url(y, m),
								selected: y == year && m == month});
					 }

					 menu.push({ item: y,
						     url: packrat.calendar.calendar_url(y),
						     sub: monthmenu,
						     collapse: true,
						     visible: y == year,
						     selected: y == year });
				     }

				     packrat.sidebar.menu(el, menu);
				 });
};
