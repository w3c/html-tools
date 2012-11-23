#!/usr/bin/env node

var fs = require("fs")
,   pth = require("path")
,   bisect = process.argv[2] === "bisect"
,   target = process.argv[3]
,   seen = {}
,   line = 0
// are we in scratch or in the tools?
// you need to copy this tool outside the repo (I use a "scratch" directory next to the repo)
// if you want to use it with git bisect -- otherwise bisect loses the tools as it tracks back
// in history (of course, stupid Robin)
,   path = pth.join(__dirname, /\/scripts/.test(__dirname) ? "../source" : "../html/source" )
;

// To use this standalone:
//      node scripts/check-split-markers.js
//    or to get just e.g. w3c-html
//      node scripts/check-split-markers.js foo w3c-html
//    yes, the "foo" there is required. Anything except "bisect" should work.
//    yes that's ugly. it's a throwaway script

// To use this with git bisect (first commit is b3b9bbc9fca6553b70cba5f33c56e2b45f3f4ec1):
//      git bisect start HEAD commitKnownToBeGood -- source
//      git bisect run node ../scratch/check-split-markers.js bisect w3c-html
//  and when done
//      git bisect reset

fs.readFileSync(path, "utf8")
    .replace(/(?:<!--(START|END)\s+([-\w]+?)-->|(\n))/g, function (match, status, key, nl, offset) {
        if (nl) {
            line++;
        }
        else {
            if (target && target !== key) return match;
            if (seen[key]) {
                if (status === seen[key]) {
                    if (bisect) process.exit(1);
                    console.log("Consecutive " + status + " for " + key + " at " + offset + " line " + line);
                }
            }
            else {
                if (status === "END") {
                    if (bisect) process.exit(1);
                    console.log("First occurrence of " + key + " is END");
                }
            }
            seen[key] = status;
        }
        return match;
    })
;

