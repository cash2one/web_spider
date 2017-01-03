var page = require('webpage').create();
page.onResourceRequested = function (request) {
 console.log('Request ' + JSON.stringify(request, undefined, 4));
};
page.onResourceReceived = function (response) {
 console.log('Receive ' + JSON.stringify(response, undefined, 4));
};
page.open("http://127.0.0.1:14887/ajax");