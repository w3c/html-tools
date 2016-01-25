exports.name = "proper-sections";
exports.transform = function() {
  var main = document.documentElement.querySelector("main");
  var fix_set = [ "index", "references", "property-index", "idl-index"];
  for (var i = 0; i < fix_set.length; i++) {
    var id = fix_set[i];
    var element = document.getElementById(id);
    var elements = [];
    var done = false;
    while (!done) {
      elements.push(element);
      element = element.nextElementSibling;
      if (element === null || element.tagName === "H2")
        done = true;
    }
    var sec = document.createElement("section");
    elements.forEach(function (e) {
      sec.appendChild(e);
    });
    main.appendChild(sec);
  }
  return document.querySelectorAll("*[id]").length;
};

