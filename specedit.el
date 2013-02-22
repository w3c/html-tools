;;; specedit.el --- Utilities for editing the HTML5 spec in Emacs

;; Author: Edward O'Connor <eoconnor@apple.com>
;; Keywords: docs, convenience

;;; Commentary:

;; There are basically four things of interest in this file:

;; 1. The command `specedit-insert-boilerplate', which is useful when
;;    replying to Bugzilla bugs.
;; 2. `specedit-mode', a major mode for editing the spec. It syntax
;;    highlights the various processing directives that we use to
;;    generate multiple specs out of the same document.
;; 3. The command `specedit-specs-at-point' will tell you what specs the
;;    character at point appears in. Helpful for when you're trying to
;;    figure out what START or END directives to add/remove.
;; 4. The command `specedit-insert-inert-block-at-point' will insert the
;;    appropriate amount of START and END directives so that the content
;;    they surround will only appear in the given spec.

;;; Code:

(autoload 'format-spec "format-spec")
(autoload 'format-spec-make "format-spec")
(autoload 'json-read-file "json")

;;; Bugzilla

(defvar specedit-boilerplate
  "EDITOR'S RESPONSE: This is an Editor's Response to your comment. If you are
satisfied with this response, please change the state of this bug to CLOSED. If
you have additional information and would like the Editor to reconsider, please
reopen this bug. If you would like to escalate the issue to the full HTML
Working Group, please add the TrackerRequest keyword to this bug, and suggest
title and text for the Tracker Issue; or you may create a Tracker Issue
yourself, if you are able to do so. For more details, see this document:

   http://dev.w3.org/html5/decision-policy/decision-policy.html

Status: %s
Change Description: %d
Rationale: %r")

(defvar specedit-statuses
  '("Accepted" "Partially Accepted" "Rejected"
    "Additional Information Needed"))

(defun specedit-insert-boilerplate (status change-description rationale)
  (interactive
   (list
    (completing-read "Status: " specedit-statuses)
    (read-string "Change Description: ")
    (read-string "Rationale: ")))
  (insert (format-spec
   specedit-boilerplate
   (format-spec-make
    ?s status
    ?d change-description
    ?r rationale))))



;;; Spec editing

(defvar specedit-preprocessor-keywords
  '("ACKS"
    "EN"
    "INTERFACES"
    "REFS"
    "toc")
  "Keywords that I think get used by the preprocessor.")

(defvar specedit-w3c-but-not-html5
  '("2DCANVAS"
    "2DCONTEXT"
    "MD"
    "POSTMSG")
  "These features have a home at the W3C outside of HTML5.")

(defvar specedit-reasons-for-forks
  '("APPCACHE-PREFER-ONLINE"
    "CONFORMANCE"
    "CSSREF"
    "DATA"
    "DOWNLOAD"
    "FIND"
    "FORM-DIALOG"
    "HPAAIG"
    "HTML4POLICE"
    "INERT"
    "PING"
    "POLITICS"
    "TITLE"
    "VERSION")
  "Markers that indicate why a fork has happened.")

(defvar specedit-explanatory-markers
  '("data-component"
    "w3c-html"
    "websocket-api")
  "Markers that indicate what spec this part ends up in.
Helpful for when there are lots of START and END directives nearby.")

(defvar specedit-feature-work-markers
  '("CLOSE CODE"
    "CODECS"
    "DND-v3"
    "DND-v4"
    "DONAV"
    "FETCH"
    "MONTHS"
    "SYNCLOAD")
  "Markers that indicate some feature work that needs to be done.")

;; FIXME: multiline highlighting
(defvar specedit-font-lock-keywords
  `(;; Commands that our editing infrastructure supports.
    ("<!--\\(BOILERPLATE\\) \\([A-Za-z0-9-.]+\\)-->"
     (1 font-lock-keyword-face)
     (2 font-lock-function-name-face))
    ("<!--\\(END\\|START\\) \\([A-Za-z0-9-]+\\)-->"
     (1 font-lock-keyword-face)
     (2 font-lock-function-name-face))
    ("<!--\\(INSERT\\) \\([A-Z]+\\)-->"
     (1 font-lock-keyword-face)
     (2 font-lock-variable-name-face))
    ("<!--\\(PUB-[NY]\\)-->\\(.*\\)$"
     (1 font-lock-keyword-face)
     (2 font-lock-string-face))
    ("<!--\\(SET\\) \\([A-Z]+\\)=\\(.+\\)-->"
     (1 font-lock-keyword-face)
     (2 font-lock-variable-name-face)
     (3 font-lock-string-face))
    ("<!--\\(FIXUP\\) \\([A-Za-z0-9-]+\\) \\([+-][0-9]+\\)-->"
     (1 font-lock-keyword-face)
     (2 font-lock-function-name-face)
     (3 font-lock-constant-face))

    ;; Commands that our editing infrastructure doesn't support get
    ;; highlighted in `font-lock-warning-face'.
    ("<!--\\(DEFER\\)\\(\\( +[A-Za-z0-9-]+\\)+\\)-->"
     (1 font-lock-warning-face)
     (2 font-lock-function-name-face))
    ("<!--\\(REFERENCES\\) \\(ON\\|OFF\\)-->"
     (1 font-lock-warning-face)
     (2 font-lock-constant-face))
    ("<!--\\(\\(?:\\(?:ADD\\|REMOVE\\)-\\)?TOPIC\\):\\(.+\\)-->"
     (1 font-lock-warning-face)
     (2 font-lock-doc-face))

    ;; Some kind of other preprocessor markers
    (,(concat "<!--"
              (regexp-opt specedit-preprocessor-keywords t)
              "-->")
     (1 font-lock-preprocessor-facefont-lock-doc-face))

    ;; Structured comments that are meant for humans, not machines.

    ("<!--\\(WARNING\\)"
     (1 font-lock-warning-face))
    ;; "Issues that are known to the editor but cannot be currently
    ;; fixed because they were introduced by W3C decisions."
    ("<!--!-->" . font-lock-warning-face)
    ;; "Known problems that are expected to be resolved in the future."
    ("XXX" . font-lock-warning-face)
    ;; Areas of divergence between the WHATWG and the W3C HTML WG. Per
    ;; our Charter, we should be aiming to reduce the number of these
    ;; over time.
    ("<!--FORK-->" . font-lock-warning-face)
    ;; Markers which indicate why the specs have forked at that
    ;; particular point
    (,(concat "<!--" (regexp-opt specedit-reasons-for-forks t))
     (1 font-lock-doc-face))
    ;; Markers which indicate what spec the following content shows up
    ;; in, for when lots of ENDs and STARTs make it confusing
    (,(concat "<!--"
              (regexp-opt specedit-explanatory-markers t)
              "-->")
     (1 font-lock-doc-face))
    ;; Markers which indicate features defined in the WHATWG spec that
    ;; have a non-HTML5 W3C spec.
    (,(concat "<!--"
              (regexp-opt specedit-w3c-but-not-html5 t)
              "-->")
     (1 font-lock-doc-face))
    ;; Markers which indicate feature work Ian expects to do in the
    ;; future.
    (,(concat "<!--"
              (regexp-opt specedit-feature-work-markers t))
     (1 font-lock-doc-face))
    ;; Ian editorializing about W3C decisions
    ("<!--\\(\\s-?EDITORIAL\\)"
     (1 font-lock-comment-face)))
  "Syntax highlighting for spec processor directives etc.")

(define-derived-mode specedit-mode fundamental-mode "HTML5 Spec"
  "Major mode for editing the HTML5 specification."
  (set (make-local-variable 'font-lock-defaults)
       '(specedit-font-lock-keywords t)))

(defun specedit-specs-at-point (p)
  "Displays which specs the character at point will appear in."
  (interactive "d")
  (save-excursion
    (goto-char (point-min))
    (let (specs
          (hitmap (make-hash-table :test 'equal)))
      ;; do work
      (while (re-search-forward
              "<!--\\(END\\|START\\) \\([A-Za-z0-9-]+\\)-->" p t)
        (puthash (match-string-no-properties 2)
                 (string-equal (match-string 1) "START")
                 hitmap))
      ;; display result
      (maphash (lambda (spec applies-at-point)
                 (when applies-at-point
                   (push spec specs)))
               hitmap)
      (when (called-interactively-p)
        (message "Appears in %s."
                 (if specs
                     (mapconcat 'identity specs ", ")
                   "no specs")))
      specs)))

(defun specedit-insert-inert-block-at-point (p spec)
  "Insert STARTs and ENDs for a block with just SPEC."
  (interactive
   (list (point)
         (completing-read "Spec: "
                          '("w3c-html" "2dcontext"))))
  (let ((specs (specedit-specs-at-point p))
        (frob-self t))
    (mapc (lambda (s)
            (if (string-equal s spec)
                (setq frob-self nil)
              (unless (string-equal s "validation")
                (insert (format "<!--END %s-->" s)))))
          specs)
    (if frob-self
        (insert (format "<!--START %s-->" spec))
      (insert (format "<!--%s-->" spec)))
    (insert "\n")
    (mapc (lambda (s)
            (unless (member s (list spec "validation"))
              (insert (format "<!--START %s-->" s))))
          specs)
    (when frob-self
      (insert (format "<!--END %s-->" spec)))
    (insert "\n")))



;;; Spec building

(defconst specedit-config-file
  (expand-file-name "default-config.json"
                    (file-name-directory (locate-library "specedit")))
  "The file that contains our publish.py configuration.")

(defconst specedit-config
  (json-read-file specedit-config-file)
  "The configuration we feed into publish.py.")

(defvar specedit-specs
  (mapcar (lambda (entry)
            (symbol-name (car entry)))
          specedit-config)
  "A list of strings naming each of our deliverables.")

(defun specedit-publish (spec)
  "Wrapper around `compile' for Anolis."
  (interactive (list (completing-read "Spec: " specedit-specs)))
  (compile (format "python ../tools/publish.py %s" spec)))

(provide 'specedit)
;;; specedit.el ends here
