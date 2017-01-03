debugger;


var port, server, service,
  wait_before_end = 1000,
  system = require('system'),
  webpage = require('webpage');

if (system.args.length !== 2)
{
  console.log('Usage: simpleserver.js <portnumber>');
  phantom.exit(1);
}
else
{
  port = system.args[1];
  server = require('webserver').create();
  console.debug = function(){};

  service = server.listen(port,
  {'keepAlive': false},
  function (request, response)
  {

    phantom.clearCookies();

    //console.debug(JSON.stringify(request, null, 4));
    // check method
    if (request.method == 'GET') {
      body = "method not allowed!";
      response.statusCode = 403;
      response.headers = {
        'Cache': 'no-cache',
        'Content-Length': body.length
      };

      response.write(body);
      response.closeGracefully();
      return;
    }

    var first_response = null,
        finished = false,
        page_loaded = false,
        start_time = Date.now(),
        end_time = null,
        script_executed = false,
        script_result = null;

    var fetch = JSON.parse(request.postRaw);

    console.debug(JSON.stringify(fetch, null, 2));

    // create and set page
    var page = webpage.create();
    page.onConsoleMessage = function(msg) {
        console.log('console: ' + msg);
    };
    page.viewportSize = {
      width: fetch.js_viewport_width || 1024,
      height: fetch.js_viewport_height || 768*3
    }
    if (fetch.headers) {
      fetch.headers['Accept-Encoding'] = undefined;
      fetch.headers['Connection'] = undefined;
      fetch.headers['Content-Length'] = undefined;
    }
    if (fetch.headers && fetch.headers['User-Agent']) {
      page.settings.userAgent = fetch.headers['User-Agent'];
    }
    // this may cause memory leak: https://github.com/ariya/phantomjs/issues/12903
    page.settings.loadImages = fetch.load_images === undefined ? true : fetch.load_images;
    page.settings.resourceTimeout = fetch.timeout ? fetch.timeout * 1000 : 20*1000;
    if (fetch.headers) {
      page.customHeaders = fetch.headers;
    }


    var render = require('./render.js');
    // send request


    render.open(page, fetch, response);
    //return "sd"

  });

  if (service) {
    console.log('phantomjs webproxy running on port ' + port);
  } else {
    console.log('Error: Could not create web server listening on port ' + port);
    phantom.exit();
  }
 }
