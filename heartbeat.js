#!/usr/bin/env node

var fs  = require("fs.extra")
,   pth = require("path")
,   exec = require("child_process").exec
,   jsdom = require("jsdom")
,   wrench = require("wrench")
;

// basic setup
var target = process.argv[2] || "html"
,   fullConf = {
        html:   {
            outDir:     "heartbeat"
        ,   make:       "html"
        ,   makeDir:    "output/html/"
        }
    ,   "2d":    {
            outDir:     "heartbeat-2d"
        ,   make:       "2dcontext"
        ,   makeDir:    "output/2dcontext/"
        }
    ,   microdata:    {
            outDir:     "heartbeat-md"
        ,   make:       "microdata"
        ,   makeDir:    "output/microdata/"
        }
    }
,   conf = fullConf[target]
,   rootDir = pth.join(__dirname, "..")
,   hbDir = pth.join(rootDir, conf.outDir)
;

if (target !== "microdata") console.log("WARNING: This script is now only required for microdata. Use make instead.");

if (fs.existsSync(hbDir)) wrench.rmdirSyncRecursive(hbDir);
fs.mkdirSync(hbDir);

// build the spec
exec("make " + conf.make, { cwd: rootDir }, function (err, stdout, stderr) {
    console.log(stdout);
    console.log(stderr);
    if (err) throw err;
    wrench.copyDirSyncRecursive(pth.join(rootDir, conf.makeDir), hbDir);
    if (target === "microdata") {
        // move HTMLPropsCol section around
        var file = pth.join(hbDir, "Overview.html");
        jsdom.env(
            file
        ,   [pth.join(rootDir, "scripts/jquery.min.js")]
        ,   function (err, window) {
                if (err) return console.log(err);
                var $ = window.$
                ,   doc = window.document
                ;
                // move HTMLProp to inside Microdata APIs
                var $toc = $("ol.toc").first()
                ,   $mdOL = $toc.find("a[href=#htmlpropertiescollection]").parent().parent()
                ,   $apiLI = $toc.find("a[href=#microdata-dom-api]").parent()
                ;
                $apiLI.append($mdOL);
                
                //  - also move the actual section
                var $hpTit = $("#htmlpropertiescollection")
                ,   sectionContent = [$hpTit]
                ,   $nxt = $hpTit.next()
                ;
                while (true) {
                    if ($nxt.is("h1,h2,h3,h4,h5,h6")) break;
                    sectionContent.push($nxt);
                    $nxt = $nxt.next();
                }
                var $other = $("#other-changes-to-html5");
                for (var i = 0, n = sectionContent.length; i < n; i++) $other.before(sectionContent[i]);
                
                // fixing the numbering, HARDCODED in the hope that we'll get a fix
                var fixNum = function ($target) {
                    $target.find(".secno").first().text("6.1 ");
                };
                fixNum($mdOL);
                fixNum($hpTit);
                console.log("WARNING: applying hardcoded section numbering fix, please check.");
                
                // serialise back to disk...
                $(".jsdom").remove();
                fs.writeFileSync(file, doc.doctype.toString() + doc.innerHTML, "utf8");
            }
        );
    
    }
});
