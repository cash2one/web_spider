

exports.open = function(page, fetch, response) {

    var url = fetch.url,
        opt = fetch;
    var pageTimeoutTimer;

    var utils = require('./utils.js'),
        headers = require('./headers.js').init(phantom, page),
        eventHandler = require('./events.js'),
        events = eventHandler.init(phantom, page),
        t = Date.now(),
        output = {}, ret = null;

    var wait_before_end = 1000,
        first_response = null,
        finished = false,
        page_loaded = false,
        start_time = Date.now(),
        end_time = null,
        script_executed = false,
        script_result = null;

    function make_result(ret) {

        var body =  {
            orig_url: fetch.url,
            status_code: 200,
            error: ret.errorString,
            content:  ret,
            headers: headers,
            url: page.url || fetch.url,
            cookies: {},
            time: (Date.now() - start_time) / 1000,
            js_script_result: script_result,
            save: null
        }
        ///page.close()
        response.writeHead(200, {
            'Cache': 'no-cache',
            'Content-Type': 'application/json',
        });

        var body = JSON.stringify(body, null, 2);
        response.write(body);
        response.closeGracefully();
    }

    function quit() {
        try {
            events.invokeListeners('onExit')
        } catch (e) {};
        utils.printJSON('exit', 0);
        phantom.exit();
    }

    // ensure that when our code fails, we could die gracefully
    phantom.onError = function (message, trace) {
        // prepare the JSON to directly die, without going thru events.notifyError()
        utils.printJSON('error', {
            errorCode: 2001,
            errorString: message + ' \r\n' + JSON.stringify(trace)
        });
        //quit();
    }

    // log the js error generated by the page
    page.onError = function (msg, trace) {
        utils.pageChanges.push('jsError', msg);
    }

    // the centralized (except phantom.onError) error handler
    events.addListener('MainFrameError', function (response) {
        // if (!response.errorCode) return;

        output.elasped = Date.now() - t;
        output.errorCode = response.errorCode;
        output.errorString = response.errorString;

        // http error with a proper status code is considered ok for scrapy
        var jsonType = 'error';
        if (response.status && response.status > 0) {
            output.ok = 1;
            jsonType = 'domSteady';
        }

        // during error, make sure phantom can die no matter what
        try {
            output.response = utils.prepareResponse(response, headers.getRespHeaders);
            output.response.body = '';//utils.cleanResponseBody(page.content);
            output.response.details = utils.pageChanges.fetchAll();
        } catch (e) {}

        //utils.printJSON(jsonType, output);
        //quit();
    });

    // validate the url
    if (utils.invalidUrl(url))
        return events.notifyError(1000, 'Invalid Url');

    // impose a strict timeout in case this phantomjs does not die properly (180s is the default by scrapy)
    opt.timeout = opt.timeout || 180;
    function setPageTimeout(timeout) {
        window.clearTimeout(pageTimeoutTimer);
        pageTimeoutTimer = window.setTimeout(function () {
            utils.printJSON('error', {
                errorCode: 4,
                errorString: 'Timeout Error (exceeded ' + opt.timeout + 's)',
                response: {
                    url: url
                }
            });
            //quit();
        }, timeout || (opt.timeout * 1000));
    }
    setPageTimeout();

    opt.debug = opt.debug || false;
    opt.method = opt.method || 'get';
    opt.data = opt.data || null;
    opt.startHostname = utils.getHostname(url);

    // whitelist the domain from url when allowed_domains are not provided
    opt.allowed_domains = opt.allowed_domains || [opt.startHostname];

    // by default no follow pre-redirections (post-redirections are not followed anyway)
    opt.followPreRedirections = opt.followPreRedirections || false;

    // if enabled, do not quit when utils.whitelistedRedirectionDomains(redirectUrl)
    opt.relaxFirstRedirection = opt.relaxFirstRedirection || true;

    // resource timeout should not exceed 30s
    page.settings.resourceTimeout = (opt.resourceTimeout || 30) * 1000;

    // make loadImages default to false
    page.settings.loadImages = (opt.loadImages = (!opt.loadImages === false));

    // to handle any headers-related manipulation and configuration
    page.customHeaders = headers.setReqHeaders(opt.headers || {}, opt.startHostname);

    // if (opt.debug) {
    // console.log('Cookies: ' + JSON.stringify(phantom.cookies));

    //     events.addListener('LoadFinished', function(status) {
    //         console.log('debug: onLoadFinished');
    //         var timeCounter = 1;
    //         window.setInterval(function(){console.log('debug: onLoadFinished + '+ (timeCounter++) +'00ms: linkCount=' + page.evaluate(function(){return document.getElementsByTagName('a').length}) )}, 100);
    //     });

    //     events.addListener('MainFrameSteady', function(response) {
    //         console.log('debug: MainFrameSteady - linkCount=' + page.evaluate(function(){return document.getElementsByTagName('a').length}) + '\n\n');
    //     });
    // }


    // stop the first url from navigating to disallowed_domains or disallowed extension (css, zip, etc)
    if (utils.invalidUrl(url, opt.allowed_domains))
        events.notifyError(1002, 'Load Failed Error (from disallowed domains)');
    else if (utils.blacklistedUrl(url))
        events.notifyError(1003, 'Filetype unsupported/unrendered as derived from file extension');

    // log all mainFrame navigations
    events.addListener('MainFrameRedirection', function (requestData, networkRequest) {
        utils.pageChanges.push('mainFrame', requestData);
    });

    events.addListener('MainFramePreRedirection', function (requestData, networkRequest) {
        // abort any request that attempts to redirect the mainframe away if nofollows is configured
        if (!opt.followPreRedirections) {
            // mainFrameSteady will still be invoked during onLoadFinished
            networkRequest.abort();
            return;
        }

        var redirectUrl = requestData.url;
        // prevent navigations to disallowed domains
        if (utils.invalidUrl(redirectUrl, opt.allowed_domains)) {

            // exception: do not abort the first redirection to some whitelisted domains
            if (opt.relaxFirstRedirection
                && !output.firstRedirectionRelaxed
                && utils.whitelistedRedirectionDomains(redirectUrl)) {
                output.firstRedirectionRelaxed = true;
                return;
            }

            networkRequest.abort();
            events.notifyError(1002, 'Load Failed Error (from disallowed domains)');
        }

        // prevent navigations to some blacklisted extensions (e.g, css, binaries)
        if (utils.blacklistedUrl(redirectUrl)) {
            networkRequest.abort();
            events.notifyError(1003, 'Filetype unsupported/unrendered as derived from file extension');
        }
    });

    // disable any navigations after reaching its first destination (i.e. no more redirects)
    events.addListener('MainFramePostRedirection', function (requestData, networkRequest) {
        // further page load will be freezed
        // using page.navigationLocked = true; won't allow us to capture the request
        networkRequest.abort();
    });

    // extract all childFrames navigations
    events.addListener('ChildFrameNavigate', function (requestData, networkRequest, type) {
        // abort any disallowed requests
        if (utils.invalidUrl(requestData.url, opt.allowed_domains) || utils.blacklistedUrl(requestData.url))
            networkRequest.abort();
        utils.pageChanges.push('childFrames', requestData);
    });

    events.addListener('MainFrameResourceReceived', function (response) {
        // phantomjs does not fetch binaries anyway
        if (response.status && response.status >= 200 && response.status < 300
            && !/(?:^text\/|xml|javascript|json)/i.test(response.contentType))
            events.notifyError(1003, 'Filetype unsupported/unrendered (' + response.contentType + ')');
    });

    events.addListener('MainFrameNavigationsEnded', function (response) {
        output.response = utils.prepareResponse(response, headers.getRespHeaders);
    });

    // skip downloading unnecessary subresources according to a known file extension list
    events.addListener('SubResourceRequested', function (requestData, networkRequest) {
        // prevent navigations to some blacklisted extensions (e.g, css, binaries)
        if (utils.blacklistedUrl(requestData.url))
            networkRequest.abort();

        // utils.pageChanges.push('subResources', requestData);
    });

    // in onInitialized, ajax calls are hooked
    events.addListener('Initialized', function () {

        // page.injectJs('./incl/jquery-2.1.1.min.js');

        // inject scripts to catch links
        page.injectJs('./extractors.js');
    });

    function extractDetails() {
        // childFrames, subResources, redirects extracted
        var extracted = {},
            details = utils.pageChanges.fetchAll();

        extracted = page.evaluate(function () {
                // link, form, and jsLink extractions
                return window._gryffin_onMainFrameReady && window._gryffin_onMainFrameReady();
            }) || {};

        //   console.log("DEBUG!!! " + page.title);
        // var cookies = page.cookies;

        // console.log('Listing cookies:');
        // for(var i in cookies) {
        //   console.log(cookies[i].name + '=' + cookies[i].value);
        // }
        details.links = extracted.links || [];
        details.forms = extracted.forms || [];

        details.jsLinkFeedback = extracted.jsLinkFeedback;

        return details;
    }

    events.addListener('MainFrameSteady', function (response) {
        // extend timeout to allow sufficient time for event enumerations
        setPageTimeout();

        // here we terminate this process with the response we collected

        output.elasped = Date.now() - t;
        output.response.body = "";//utils.cleanResponseBody(response.body);

        if (opt.htmlOnly) {
            console.log("console.log" + output.response.body);
            phantom.exit();
            return;
        }

        ret = output.response.details = extractDetails();

        // ensure only one JSON is outputed
        if (!output.ok) {
            output.ok = 1;
            // console.log(JSON.stringify(output, function(k, v){
            //     return (typeof v === "string")
            //             ? v.replace(/[\u007f-\uffff]/g, function(c) {
            //                     return '\\u'+('0000'+c.charCodeAt(0).toString(16)).slice(-4);
            //                 });
            //             : v;
            // }));
            //utils.printJSON('domSteady', output);
            //make_result(output);
            //end_time = Date.now() + wait_before_end;
            setTimeout(make_result, wait_before_end+10, output);
        }

        // can exit due to lack of jsLinks execution
        //if (output.response.details && !output.response.details.jsLinkFeedback)
        //quit();
    });

    // disable any navigations from new windows, instead, capture the request object
    events.addListener('PageCreated', function (newPage) {

        var newEvents = eventHandler.init(phantom, newPage);
        newEvents.addListener('ResourceRequested', function (requestData, networkRequest) {
            networkRequest.abort();
            utils.pageChanges.push('childFrames', requestData);
        });
    });

    // get informed about new link discovery by incl/extractors.js
    events.addListener('Callback', function (data) {
        if (data.action === 'waitTimer') {
            events.invokeListeners('onSteady-waitTimer', data.timeout);

        } else if (data.action === 'element.triggering') {
            // wait for network steady once an element is being triggered
            events.addListener('onSteady', function () {
                var eventData = page.evaluate(function () {
                        return jsLinks.getData()
                    }),
                    // associate other page changes to the recent element triggered
                    changes = utils.pageChanges.fetchAll();
                changesKeys = Object.keys(changes);

                // append any pageChanges to the eventData
                changesKeys.forEach(function (k) {
                    eventData[k] = changes[k];
                });

                // if there exists any dom changes
                if (changesKeys.length > 0 || eventData.links || eventData.forms)
                    events.invokeListeners('onDomChanged', eventData);

                // by design, onSteady is called only once even without "return false"
                return false;
            });
            events.invokeListeners('onSteady-wait', 'element-trigger');
        } else if (data.action === 'element.triggered') {
            events.invokeListeners('onSteady-ready', 'element-trigger');
        } else if (data.action === 'done')
            quit();
    });

    // print the triggered element if new results are available
    events.addListener('DomChanged', function (data) {
        setTimeout(make_result, wait_before_end+10, data);
        //utils.printJSON('domChanged', data);
    });

    // page.onConsoleMessage = function(msg) {
    //     console.log('CONSOLE: ' + msg);
    // };
    page.onConfirm = function (msg) {
        return true
    };



    page.openUrl(url, {
        operation: opt.method,
        data: opt.data // String expected
    }, page.settings);


}