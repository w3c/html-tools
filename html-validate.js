#!/usr/bin/env node

var fs  = require("fs")
,   pth = require("path")
,   request = require("request")
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
    
    // validate HTML
    var url = (process.argv[3] ? process.argv[3] : "http://berjon.com/TR/html5/") + file
    // ,   valid = "http://validator.w3.org/check?uri=" + encodeURIComponent(url)
    ,   valid = "http://html5.validator.nu/?out=json&doc=" + url
    ;
    
    // html validation
    request({ url: valid, method: "GET"}, function (err, resp, body) {
        if (err) return console.log(err);
        // if (resp.headers["x-w3c-validator-errors"] !== "0") console.log("Error, check " + valid);
        // else console.log("\tHTML OK!");
        var res = JSON.parse(body)
        ,   msg = []
        ;
        for (var i = 0, n = res.messages.length; i < n; i++) {
            var m = res.messages[i];
            if (m.type === "error") msg.push(m);
        }
        if (msg.length !== 0) console.log("Error, check " + valid, msg);
        else console.log("\tHTML OK!");
        pubrules();
    });
}

pubrules();
