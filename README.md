Tools used to publish the HTML WG drafts
========================================

This repository contains all the tools that are being used to publish
the following specifications of the HTML WG:

* HTML
* Canvas
* Microdata

Support for further specifications may be added as things progress.

Installation
============

Just check it out wherever seems convenient to you, and it should work. Its
one dependency is a recent version of [Anolis](https://bitbucket.org/ms2ger/anolis/).

Configuration
=============

There is a `default-config.json` file included here. Do ***NOT*** edit it, it
is just the default. If you need to override its values, create a `local-config.json`
file and use it to override just the values you need. For instance, if you
need your HTML draft to be in `/some/other/path` (the default assumes `../html`), just
create this `local-config.json`:

```json
{
    "html": { "path": "/some/other/path" }
}
```

Running
=======

You can run this either as:

    python publish.py [html|2dcontext|microdata]

or as:

    make [html|2dcontext|microdata]


