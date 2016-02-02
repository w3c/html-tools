#!/usr/bin/env node
/*jshint -W054 */

var Nightmare = require('nightmare');
var vo = require('vo');
var io = require('./io-promise');

// Split the HTML spec into multipages
//
// load the document into a browser,
// do one small cleanup for sections
// remap all the hrefs based on section files
// for each document/section,
//   clone the main document
//   remove what's unnecessary
//   add some navbars
//   dump the output into a file

//var specURL = 'file://' + __dirname + "/../single-page.html";
var specURL = "https://w3c.github.io/html/single-page.html";
var baseOutputURL = './out/';

if (process.argv[2] !== undefined
    && process.argv[3] !== undefined) {
  specURL = process.argv[2];
  baseOutputURL = process.argv[3];
}

var sections = [
      "introduction"
  ,   "infrastructure"
  ,   "dom"
  ,   "semantics"
  ,   "editing"
  ,   "browsers"
  ,   "webappapis"
  ,   "syntax"
  ,   "xhtml"
  ,   "rendering"
  ,   "obsolete"
  ,   "iana"
  ,   "index"
  ,   "property-index"
  ,   "idl-index"
  ,   "references"
  ,   "acknowledgements"
];

var rules = [];

var ruleSet = [
//  "proper-sections"
];

ruleSet.forEach(function (lib) {
  rules.push(require("./rules/" + lib));
});

function* run() {

  var nightmare = Nightmare();
  var spec = nightmare
    .goto(specURL);
  var i, id;

  // first yield for the document to load
  console.log("loading " + specURL);
  var title = yield spec
    .evaluate(function() {
      return document.title;
    });

  console.log("Found " + title);

  // do whatever cleanup as defined by the rules
  //   can't use forEach here because of the yield :-/
  console.log("Applying preprocessing rules");
  for (i = 0; i < rules.length; i++) {
    var rule = rules[i];
    console.log("  " + rule.name);
    yield spec
      .evaluate(rule.transform);
  }

  // rewrite the links

  // first, create a mapping between the ids and their files
  var ret = '';
  for (i = 0; i < sections.length; i++) {
    id = sections[i];
    ret += yield spec
      .evaluate(function(id) {
        var destfile = id;
        if (destfile === "index") {
          destfile = "fullindex";
        }
        var ret = "";
        if (window.idMap === undefined) {
          window.idMap = [];
        }
        var section = document.getElementById(id).parentNode;
        while (section.tagName !== "SECTION") {
          section = section.parentNode;
        }
        var elements = section.querySelectorAll("*[id]");
        for (var i = 0; i < elements.length; i++) {
          window.idMap["#" + elements[i].id] = id;
          ret += '"#' + elements[i].id + '":"' + destfile + '"\n';
        }
        return ret;
      }, id);
  }
  // (save that for future analysis/debugging)
  io.save(baseOutputURL + "logs/idmap.txt", ret);

  // second, rewrite the href to match the mapping
  var links = yield spec
      .evaluate(function() {
        var ret = "";
        if (window.idMap === undefined) {
          return "oops";
        }
        var links = document.querySelectorAll("a[href^='#']");

        for (var i = 0; i < links.length; i++) {
          var link = links[i];
          var href = link.getAttribute("href");
          if (window.idMap[href] !== undefined) {
            link.href = window.idMap[href] + ".html" + href;
          } else {
            ret += href + "\n";
          }
        }

        return ret;
      });

  if (links !== "") {
    // (save that for future analysis/debugging)
    io.save(baseOutputURL + "logs/link_errors.text", links);
  }


  console.log("Generating index");
  var overview = yield spec
      .evaluate(function() {
        var doc = document.documentElement.cloneNode(true);
        var body = doc.children[1];
        var children = body.children;
        var found = false;
        for (var i = children.length - 1; i >=  0 && !found; i--) {
          found = (children[i].tagName === "MAIN");
          body.removeChild(children[i]);
        }

        return "<!DOCTYPE html>\n" + doc.outerHTML;
      });
  io.save(baseOutputURL + "index.html", overview);


  console.log("Generating sections");
  for (i = 0; i < sections.length; i++) {
    id = sections[i];
    console.log("  " + id);
    var sec = yield spec
      .evaluate(function(id) {
      try {
        var doc = document.documentElement.cloneNode(true);

        // remove unnecessary heading (Version links, editors, etc.)
        var current = doc.querySelector("h2#abstract");
        var nextElement;
        do {
          nextElement = current.nextElementSibling;
          current.parentNode.removeChild(current);
          current = nextElement;
        } while (current.tagName !== "NAV");

        current = doc.querySelector("header").nextElementSibling;
        do {
          nextElement = current.nextElementSibling;
          current.parentNode.removeChild(current);
          current = nextElement;
        } while (nextElement !== null);

        // only keep the appropriate section
        var section_position = -1;
        var titleSection = "";
        var main = doc.querySelector("main");
        // nodeList are live, so start from the end to remove children
        for (var j = main.children.length - 1; j >= 0; j--) {
          var section = main.children[j];
          var h2 = section.querySelector("h2");
          if (section.tagName !== "SECTION"
              || h2 === null || h2.id !== id) {
            main.removeChild(section);
          } else {
            // we keep this section
            // remember its position and its title
            section_position = j;
            titleSection = h2.querySelector("span.content").textContent;
          }
        }

        // only keep the appropriate nav toc
        var toc = doc.querySelector("nav#toc ol");
        var tocs = toc.children;
        var previous_toc = null;
        var next_toc = null;
        for (i = tocs.length - 1; i >= 0; i--) {
          if (i !== section_position) {
            if (i === (section_position - 1)) {
              previous_toc = tocs[i];
            } else if (i === (section_position + 1)) {
              next_toc = tocs[i];
            }
            toc.removeChild(tocs[i]);
          }
        }

        // make a nice title for the document
        var titleElement = doc.querySelector("title");
        titleElement.textContent = titleElement.textContent + ": " +
          titleSection;

        // insert top and botton mini navbars
        var nav = document.createElement("nav");
        nav.className = "prev_next";
        var innerNavHTML = "<a href='index.html#contents'>"
          + "Table of contents</a>";
        if (previous_toc !== null) {
          innerNavHTML = "← "
            + previous_toc.querySelector("a").outerHTML
            + " — " + innerNavHTML;
        }
        if (next_toc !== null) {
          innerNavHTML = " — " + innerNavHTML + " →"
            + next_toc.querySelector("a").outerHTML;
        }
        nav.innerHTML = innerNavHTML;
        var mainNav = doc.querySelector("nav#toc");
        mainNav.parentNode.insertBefore(nav, mainNav);
        mainNav.parentNode.appendChild(nav.cloneNode(true));

        return "<!DOCTYPE html>\n" + doc.outerHTML;
      } catch (e) {
        // catch all so we can know what happened
        return "ERROR: " + e.message;
      }
    }, id);

    if (sec.startsWith("ERROR:")) {
      console.log("    " + sec);
    } else {
      var destfile = id;
      if (destfile === "index") {
        destfile = "fullindex";
      }
      io.save(baseOutputURL + destfile + ".html", sec);
    }
  } // end for each section

  console.log("Your documents are in " + baseOutputURL);
  yield nightmare.end();

  return "Done";
}

vo(run)(function(err, result) {
  if (err) throw err;
});
