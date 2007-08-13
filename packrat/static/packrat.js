var base = window.packrat_base;

var image_search = function(id, search, params) {
	var thumbTemplate = new Ext.Template(
		'<li><span class="image" id="img{id}">' +
		  '<span class="thumb">' + 
		    '<a href="{imgurl}" class="thickbox" rel="search-results" title="{title}">'+
		    '<img width="{width}" height={height}" src="{thumburl}" title="{title}">'+
		    '</a>' +
		  '</span>' +
		'</span></li>'
		);
	thumbTemplate.compile();

	var view = new Ext.JsonView(id, thumbTemplate, { jsonRoot: 'results', multiSelect: true });


	view.prepareData = function(p) {
		var size = 'stamp';

		return { id: p.id,
			 imgurl: p.sizes.small.url,
			 thumburl: p.sizes[size].url,
			 width: p.sizes[size].width,
			 height: p.sizes[size].height,
			 title: p.title
		}
	}

	if (!(search instanceof Array ))
		search = [ search ];

	if (params == null)
		params = {};
       	params.format = 'json';

	view.on('load', function () { tb_init('#'+id+' .thickbox'); }, null);

	view.load({
		  method: "GET",
		  url: base + 'image/-/' + search.join('/') + '/',
		  params: params,
		  text: "Loading...",
		  disableCaching: false });
}
