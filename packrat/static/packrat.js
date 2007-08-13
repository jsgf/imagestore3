var base = window.base;

var image_search = function(id, search, params) {
	this.thumbTemplate = new Ext.Template(
		'<li><span class="image" id="img{id}">' +
		  '<span class="thumb">' + 
		    '<a href="{imgurl}" rel="lightbox" title="{title}">'+
		    '<img width="{width}" height={height}" src="{thumburl}" title="{title}">'+
		    '</a>' +
		  '</span>' +
		'</span></li>'
		);
	this.thumbTemplate.compile();

	this.view = new Ext.JsonView(id, this.thumbTemplate, { jsonRoot: 'results' });


	this.view.prepareData = function(p) {
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
	
	params.format = 'json'

	this.view.on('load', initLightbox, null);

	this.view.load({
		  method: "GET",
		  url: base + 'image/-/' + search.join('/') + '/',
		  params: params,
		  text: "Loading...",
		  disableCaching: false });
}
