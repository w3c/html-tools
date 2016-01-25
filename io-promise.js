/*
 Copyright © 2015 World Wide Web Consortium, (Massachusetts Institute of Technology,
 European Research Consortium for Informatics and Mathematics, Keio University, Beihang).
 All Rights Reserved.

 This work is distributed under the W3C® Software License [1] in the hope that it will
 be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.

 [1] http://www.w3.org/Consortium/Legal/2002/copyright-software-20021231
*/

// library wrapping a few Node.js io operations around Promise

// Example:

//  io.fetch("http://www.example.org").then(function (res) {
//   return res.text();
//  })

//  io.fetch("http://www.example.com/object.json").then(function (res) {
//   return res.json();
//  })

//  io.post("http://www.example.org", {foo: "bar"} ).then(function (res) {
//   return res.text();
//  })

//  io.read("myfile.json").then(function (res) {
//   return res.json();
//  })

//  io.fetch("http://www.example.org", { delay: 2 } ).then(function (res) {
//   return res.text();
//  })

require('es6-promise').polyfill();

// that's our exposed module
var io_promise = {};

// array for monitoring
var fetches;

// Definition of a response
function Response(options) {
  this.status = options.status;
  this.url    = options.url;
  this.data   = options.data; // @@ should be a buffer
  this.headers = options.headers;
  this.text = function () {
    return Promise.resolve(this.data);
  };
  this.json = function () {
    return this.text().then(JSON.parse);
  };
}

any = function (params) {
  // console.log("Calling io_promise.any");
  var settings = {};
  var opts = (params.options === undefined)? {} : params.options;
  var delay = 0;
  if (opts.delay !== undefined) {
    delay = opts.delay * 1000; // use seconds instead of ms
  }
  settings.auth = opts.auth;
  settings.method = params.verb;
  if (opts.headers !== undefined) {
    settings.headers = JSON.parse(JSON.stringify(params.options.headers));
  }
  if (settings.headers === undefined) settings.headers = {};
  if (params.data !== undefined) {
    if (settings.headers['Content-Type'] === undefined) {
      if (typeof params.data == "object") {
        settings.headers['Content-Type'] = "application/json";
        var data = JSON.stringify(params.data);
        params.data = data;
      } else {
        settings.headers['Content-Type'] = "application/octet-stream";
      }
    }
    if (settings.headers['Content-Length'] === undefined) {
      if (typeof params.data == "string") {
        settings.headers['Content-Length'] = params.data.length;
      }
      // @@support other primitive types?
    }
  }
  var library = require((params.url.indexOf("https://") === 0)?
    "https" : "http"); // @@support "file:" ?
  if (fetches !== undefined) { // if monitoring
    fetches.push(params.url);
  }
  return new Promise(function (resolve, reject) {
    var location = require("url").parse(params.url);
    settings.hostname = location.hostname;
    settings.path = location.path;
    var req = library.request(settings, function(res) {
      var buffer = "";
      res.on('data', function (chunk) {
        buffer += chunk;
      });
      res.on('end', function () {
        var response = new Response({ status: res.statusCode,
                                 url: res.url,
                                 data: buffer,
                                 headers: res.headers });
        var fct = reject;
        if (res.statusCode >= 200 && res.statusCode < 300) {
          fct =resolve;
        }
        if (delay === 0) {
          fct(response);
        } else {
          // console.log("We're delaying...");
          setTimeout(function () {
            fct(response);
          }, delay);
        }
      });
    });
    req.on('error', function(err) {
      reject(err);
    });
    if (params.data !== undefined) req.write(params.data);
    req.end();
  });
};

io_promise.get = function (url, options) {
  return any({ verb: 'GET', url: url, options: options});
};

io_promise.head = function (url, options) {
  return any({ verb: 'HEAD', url: url, options: options});
};

io_promise.post = function (url, data, options) {
  return any({ verb: 'POST', url: url, data: data, options: options});
};

io_promise.put = function (url, data, options) {
  return any({ verb: 'POST', url: url, data: data, options: options});
};

io_promise.patch = function (url, data, options) {
  return any({ verb: 'PATCH', url: url, data: data, options: options});
};

io_promise.fetch = io_promise.get;

// File IO

function convertErrno(errno, default_value) {
  var status;
  switch (errno) {
  case 'EPERM':
  case 'EACCES':
    status = 403;
    break;
  case 'ENOENT':
    status = 404;
    break;
  case 'EISDIR':
    status = 405;
    break;
  case 'EAGAIN':
  case 'EBUSY':
  case 'ENOMEM':
    status = 408;
    break;
  case 'EFBIG':
    status = 413;
    break;
  case 'EINTR':
  case 'EIO':
  case 'ENODEV':
    status = 500;
    break;
  case 'ENOSPC':
  case 'EROFS':
    status = 503;
    break;
  default:
    status = default_value;
  }
  return status;
}

io_promise.read = function (filename, options) {
  if (options === undefined) {
    options = {  encoding: "utf-8" };
  }
  return new Promise(function (resolve, reject) {
    require('fs').readFile(filename, options, function(err, data) {
      if (err) {
        // Give proper status
        var status = convertErrno(err.code, 400);
        var path = (err.path !== undefined)? err.path : filename;
        reject (new Response({ status: status,
            data: err.message,
            url: path,
            headers: err}));
      } else {
        resolve(
          new Response({ status: 201,
            data: data,
            url: filename}));
      }
    });
  });
};

io_promise.save = function (filename, data, options) {
  if (options === undefined) {
    options = { encoding: "utf-8" };
  }
  if (typeof data == "object") {
    // Use JSON serializer for objects
    bytes = JSON.stringify(data);
  } else {
    bytes = data;
  }
  return new Promise(function (resolve, reject) {
    require('fs').writeFile(filename, bytes, options, function(err) {
      if (err) {
        var status = convertErrno(err.code, 500);
        var path = (err.path !== undefined)? err.path : filename;
        reject (new Response({ status: status,
            data: err.message,
            url: path,
            headers: err}));
      } else {
        resolve(
          new Response({ status: 201,
            data: data,
            url: filename}));
      }
    });
  });
};

// monitoring functions

io_promise.fetches = function() {
  // makes a copy
  if (fetches !== undefined) {
    return fetches.map(function (u) {
      return u;
    });
  }
};

io_promise.fetchesCount = function() {
  return (fetches === undefined)? 0 : fetches.length;
};

// turn monitoring on
io_promise.monitor = function () {
  fetches = [];
};

// Readline terminal I/O

io_promise.question = function (msg) {
  var rl = require('readline').createInterface({
    input: process.stdin,
    output: process.stdout
  });

  return new Promise(function (resolve, reject) {
    rl.question(msg, function(answer) {
      resolve(answer);
      rl.close();
    });
  });
};

// delay a promise

io_promise.wait = function (delay, continuation) {
  return new Promise(function (resolve, reject) {
    setTimeout(function () {
      var result;
      if (continuation !== undefined) {
        if (typeof continuation == "function") {
          try {
            result = continuation();
          } catch (err) {
            reject (err);
            return undefined;
          }
        } else {
          result = continuation;
        }
      }
      resolve(result);
    }, delay);}
  );
};


// End of module
module.exports = io_promise;
