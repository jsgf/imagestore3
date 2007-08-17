var packrat_init = function(base, static) {
    this.thumb_template = function(img) {
	var th = img.sizes.stamp;
	var p = img.sizes.small;

	return $.SPAN({ Class: 'thumb' },
		      $.A({ href: p.url, Class: 'thickbox', rel: 'search-results', title: img.title },
			  $.IMG({ width: th.width, height: th.height,
					src: th.url, title: img.title })));
    };

    tb_pathToImage = static + tb_pathToImage;

    return {
	// url pieces
	base: base,
	searchbase: base + 'image/-/',
	static: static,

	image_search: function(el, search, params) {
	    var result_render = function(el, data) {
		el.empty();

		for each (var img in data.results)
		    el.append($.LI({ Class: 'image', id: 'img'+img.id },
				   this.thumb_template(img)));

		tb_init($('.thickbox', el));
	    };

	    if (!(search instanceof Array ))
		search = [ search ];

	    if (params == null)
		params = {};
	    params.format = 'json';

	    $(el).jsonupdate(base + 'image/-/' + search.join('/') + '/',
			     params, result_render);
	},
    }
};

// Simple way to update an element with json:
// $(foo).jsonupdate(url, params, renderer...)
jQuery.fn.extend({
      jsonupdate: function(url, params, render) {
	    var el = this;
	    // embellishments: add "loading" spinning; error indication, etc...
	    jQuery.getIfModified(url, params, function (data) { render(el, data); }, 'json');
	}
    });


var renderMonth = function(element, year, month, days) {
};

var calendarYearView = function(element, year) {
	var search = '';
	var mgr = new Ext.UpdateManager(element);

	var upd = {
		url: searchbase + 'created:' + year,
		params: {
			format: 'calendar',
		},
		disableCaching: false,
		method: 'GET',
	};

	var month_renderer = function () {};
	month_renderer.prototype = {
		template: new Ext.Template('<ul>'+
					   ' <li id="date{year}-{month}" class="month"></li>' +
					   '</ul>'),

		render: function(el, response) {
			var y = Ext.util.JSON.decode(response.responseText)[year];

			for (var m in y) {
				this.template.append(el, { year: year, month: m });
				renderMonth($('.month', element), year, m, y[m]);
			}				
		},
	}

	mgr.renderer = new month_renderer();
	mgr.on('update', function() { element.show('slow'); })
	mgr.update(upd)
};

var calendarOverview = function(element) {
	var element = Ext.get(element);
	var mgr = element.getUpdateManager();

	var upd = {
		url: searchbase,
		params: {
			format: 'calendar',
		},
		disableCaching: false,
		method: 'GET',
	};

	var year_renderer;

	year_renderer = function() {};
	year_renderer.prototype = {
		template: new Ext.Template('<div id="year{year}">' +
					   ' <h2><a href="#">{year}</a>: {count}</h2>' +
					   ' <div class="year" style="display: none;">' +
					   '  ...' +
					   ' </div>' +
					   '</div>'),

		render: function(el, response) {
			var o = Ext.util.JSON.decode(response.responseText);

			var getCounts = function(year) {
				var count = 0;
				
				for each (var m in year)
					for each (var d in m)
						count += d.count;

				return count;
			}

			for (var y in o) {
				this.template.append(el, { year: y, count: getCounts(o[y]) });
				$('#year'+y).toggle(function () {
							    var d = $('.year', this);
							    calendarYearView(d, y);
							    return false;
						    },
						    function () {
							    $('.year', this).hide('slow');
							    return false;
						    });
			}
		},
	};

	mgr.renderer = new year_renderer();
	mgr.update(upd)
};

var displayCalendar = function(elem, year, month, day, period, search) {
	if (year == null) {
		calendarOverview(elem);
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
