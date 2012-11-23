#!/usr/bin/env node

var fs  = require("fs")
,   pth = require("path")
;

// where are we?
var srcDir = "/Projects/html/html-reference/"
,   targetDir = "/Projects/htmlwg.org/public/heartbeat/WD-html-markup-20121011/"
,   files = fs.readdirSync(srcDir)
,   total = files.length
;
console.log("Checking " + total + " files");
for (var i = 0, n = files.length; i < n; i++) {
    var file = files[i];
    console.log("Checking " + file + ", " + i + "/" + total);
    if (!/\.html$/.test(file)) continue;
    if (/^fragment-links/.test(file)) continue;
    var content = fs.readFileSync(pth.join(srcDir, file), "utf8");
    // remove crappy trailing stuff
    content = content.replace(/<\/body>\n<\/html>\npt>\n<\/body>\n<\/html>/, "</body>\n</html>\n");
    
    // find duplicate IDs
    var match = content.match(/<html id="(.*?)"/);
    if (match && match[1]) {
        content = content.replace(new RegExp("<div id=\"" + match[1] + "\""), "<div");
    }
    
    // add missing <!DOCTYPE> and meta utf8
    if (!/<!DOCTYPE html/i.test(content)) content = "<!DOCTYPE html>\n" + content;
    if (!/utf-8/i.test(content)) content = content.replace("<head>", "<head>\n<meta charset=utf-8>");
    
    fs.writeFileSync(pth.join(targetDir, file), content, "utf8");
}