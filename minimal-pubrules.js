#!/usr/bin/env node

var fs  = require("fs")
,   pth = require("path")
,   jsdom = require("jsdom")
;

// where are we?
var rootDir = __dirname
,   hbDir = process.argv[2] ? process.argv[2] : pth.join(rootDir, "heartbeat")
,   files
,   total = 0
;

function pubrules () {
    if (files.length === 0) return;
    var file = files.shift();
    console.log("Processing " + file + ", " + (total - files.length) + "/" + total);
    if (!/\.html$/.test(file)) return pubrules();
    // skip single-page, it's just too long
    if (/single-page\.html/.test(file)) return pubrules();
    
    jsdom.env(
        pth.join(hbDir, file)
    ,   [pth.join(rootDir, "jquery.min.js")]
    ,   function (err, window) {
            if (err) return console.log(err);
            var $ = window.$;
            // - right stylesheet (for the given release type)
            // - stylesheet last (of linked styles)
            var css = $("link[href='http://www.w3.org/StyleSheets/TR/W3C-WD']");
            if (!css.length) console.log("No WD style");
            if (css.nextAll("link[rel=stylesheet]").length) console.log("Stylesheets following primary one");
            // - IDs on headers
            $("h1, h2, h3, h4, h5, h6").each(function () {
                var $h = $(this);
                if ($h.attr("id")) return;
                if ($h.parent().attr("id")) return;
                console.log("Missing and ID on " + $h.text());
                // normally there can also be <a name> but we can safely ignore that
            });
            var $head = $(".head");
            // - logo
            var $a = $head.find("a[href='http://www.w3.org/']");
            if (!$a.length) console.log("Missing header logo link");
            if (!$a.find("img[src='http://www.w3.org/Icons/w3c_home']").length) console.log("Missing logo");
            // - h1 title and "W3C Working Draft 29 March 2012" in .head
            if (!$head.find("h1")) console.log("Missing h1");
            if (!/W3C Working Draft \d\d \w+ \d{4}/.test($head.find("h2").last().text())) console.log("Missing status and date");
            pubrules();
        }
    );
}

files = fs.readdirSync(hbDir);
total = files.length;
console.log("Checking " + total + " files");
pubrules();
