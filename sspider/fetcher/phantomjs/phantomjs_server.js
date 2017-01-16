/*
 phantomjs 代理服务器，渲染并提取url

 2017.1.1
 */
var cn = 0;
var port, server, service,
    system = require('system'),
    webpage = require('webpage'),
    render = require('./render.js');

if (system.args.length !== 2)
{
    console.log('Usage: phantomjs_server.js <portnumber>');
    phantom.exit(1);
}
else
{
    cn = cn + 1;
    console.log("!!!!!!!!!!!!!!!" + cn);

    port = system.args[1];
    server = require('webserver').create();
    //console.debug = function(){};

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

            var fetch = JSON.parse(request.postRaw);

            //console.debug(JSON.stringify(fetch, null, 2));

            // create and set page
            var page = webpage.create();
            page.onConsoleMessage = function(msg) {
                console.log('web console: ' + msg);
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
            else
            {
                page.settings.userAgent = "chspider0.1";
            }
            // this may cause memory leak: https://github.com/ariya/phantomjs/issues/12903
            page.settings.loadImages = fetch.load_images === undefined ? true : fetch.load_images;
            page.settings.resourceTimeout = fetch.timeout ? fetch.timeout * 1000 : 20*1000;
            if (fetch.headers) {
                page.customHeaders = fetch.headers;
            }



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
