var tl;
function onLoad() {
  var pictureSource = new Timeline.DefaultEventSource();
  var cameraSource = new Timeline.DefaultEventSource();
  var combinedSource = new Timeline.DefaultEventSource();
  var theme = Timeline.ClassicTheme.create();

  theme.ether.backgroundColors[3] = "#BBB";
  theme.event.bubble.width = 350;
  theme.event.bubble.height = 270;

  var bandInfos = [
    Timeline.createBandInfo({
	theme: theme,
        eventSource:    cameraSource,
        width:          "60px", 
        trackHeight:    1.2,
        trackGap:       0.2,
        intervalUnit:   Timeline.DateTime.DAY, 
        intervalPixels: 200
    }),
    Timeline.createBandInfo({
	theme: theme,
        eventSource:    pictureSource,
        width:          "340px", 
        trackHeight:    7.5,
        trackGap:       0.2,
        intervalUnit:   Timeline.DateTime.DAY, 
        intervalPixels: 200
    }),
    Timeline.createBandInfo({
	theme: theme,
        eventSource:    combinedSource,
        width:          "50px", 
        showEventText:  false,
        trackHeight:    0.7,
        trackGap:       0.2,
        intervalUnit:   Timeline.DateTime.MONTH, 
        intervalPixels: 200
    }),
    Timeline.createBandInfo({
	theme: theme,
        eventSource:    combinedSource,
        width:          "50px", 
        showEventText:  false,
        trackHeight:    0.5,
        trackGap:       0.2,
        intervalUnit:   Timeline.DateTime.YEAR, 
        intervalPixels: 300
    })
  ];
  bandInfos[1].syncWith = 0;
  bandInfos[1].highlight = true;
  bandInfos[2].syncWith = 0;
  bandInfos[2].highlight = true;
  bandInfos[3].syncWith = 0;
  bandInfos[3].highlight = true;
  tl = Timeline.create(document.getElementById("my-timeline"), bandInfos);
  Timeline.loadXML('/imagestore/image/timeline/', function(xml, url) { pictureSource.loadXML(xml, url); });
  Timeline.loadXML('/imagestore/camera/timeline/', function(xml, url) { cameraSource.loadXML(xml, url); });
  Timeline.loadXML('/imagestore/image/timeline/', function(xml, url) { combinedSource.loadXML(xml, url); });
  Timeline.loadXML('/imagestore/camera/timeline/', function(xml, url) { combinedSource.loadXML(xml, url); });
}

var resizeTimerID = null;
function onResize() {
    if (resizeTimerID == null) {
        resizeTimerID = window.setTimeout(function() {
            resizeTimerID = null;
            tl.layout();
        }, 500);
    }
}

function centerTimeline(date) {
    tl.getBand(0).setCenterVisibleDate(SimileAjax.DateTime.parseGregorianDateTime(date));
}
