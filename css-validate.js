#!/usr/bin/env node

var fs  = require("fs")
,   pth = require("path")
,   request = require("request")
,   libxmljs = require("libxmljs")
;

// where are we?
var rootDir = pth.join(__dirname, "..")
,   hbDir = process.argv[2] ? process.argv[2] : pth.join(rootDir, "heartbeat")
,   files = fs.readdirSync(hbDir)
,   total = files.length
;

console.log("Checking " + total + " files");


function pubrules () {
    if (files.length === 0) return;
    var file = files.shift();
    console.log("Processing " + file + ", " + (total - files.length) + "/" + total);
    if (!/\.html$/.test(file)) return pubrules();
    
    // validate CSS
    var url = (process.argv[3] ? process.argv[3] : "http://berjon.com/TR/html5/") + file
    // ,   css = "http://jigsaw.w3.org/css-validator/validator?profile=css3&output=json&uri=" + encodeURIComponent(url)
    ,   css = "http://jigsaw.w3.org/css-validator/validator?profile=css3&output=ucn&uri=" + encodeURIComponent(url)
    ;
    
    // css validation
    request({ url: css, method: "GET"}, function (err, resp, body) {
        if (err) return console.log(err);
        // XXX this works, but it gives no details and so we can't ignore errors
        // var res = JSON.parse(body);
        // if (!res.validity) console.log("Error, check " + css);
        // else console.log("\tCSS OK!");
        var doc = libxmljs.parseXml(body)
        ,   errors = doc.find("//message[@type='error']")
        ,   errCount = 0
        ;
        for (var i = 0, n = errors.length; i < n; i++) {
            var node = errors[i]
            ,   txt = node.text()
            ;
            if (/leader/.test(txt)) continue;
            errCount++;
        }
        if (errCount) console.log("Error, check " + css);
        else console.log("\tCSS OK!");
        pubrules();
    });
}
pubrules();
