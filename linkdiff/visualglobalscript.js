document.addEventListener("click", (e) => {
  if (e.target.nodeName == "A") {
    if (e.target.hasAttribute("href")) {
      if (e.target.hasAttribute("data-ld-m") || e.target.hasAttribute("data-ld-c")) { // external links are not tampered with
        e.preventDefault();
        e.stopPropagation();
        if (keyState.navToMatch) {
          // post message to navigate other windows to specific anchor.
          getGlobalOtherWindow().postMessage({findAnchor: parseInt(e.target.dataset.ldMatchIndex) }, "*");  
        }
        else {
          // normal internal link.
          let elem = document.querySelector(e.target.dataset.ldHref);
          if (elem) {
            elem.scrollIntoView();
          }
        }
      }
    }
  }
});
addEventListener("message", (e) => {
  if (e.data) {
    if (typeof e.data.findAnchor == "number") {
      let elem = document.querySelectorAll("a[href]")[e.data.findAnchor];
      alert("...scrolling to requested match");
      elem.scrollIntoView()
    }
  }
});
addEventListener("keydown", (e) => {
  if (e.keyCode == 77)
      keyState.navToMatch = true;
});
addEventListener("keyup", () => {
  keyState.navToMatch = false;
});
var keyState = { 
  navToMatch: false, /* g */
};
var globalOtherWindow = null;
function getGlobalOtherWindow() {
  if (globalOtherWindow == null) {
    if (window.opener && !window.opener.closed)
      globalOtherWindow = window.opener;
    else
      globalOtherWindow = window.open("$$OTHERFILE$$", "");
  }
  if (globalOtherWindow.closed) {
    globalOtherWindow = null;
    globalOtherWindow = getGlobalOtherWindow();
  }
  keyState.navToMatch = false;
  return globalOtherWindow;
}