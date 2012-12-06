
from email.Utils import formatdate
import os, sys, datetime
import config, publish

BOLD_GREEN = "\033[01;32m"
NO_COLOUR = "\033[0m"

# TODO
#   - generate an index page for all

def main(index_path):
    print formatdate()
    conf = config.load_config()
    if index_path:
        make_index(conf, index_path)
    for s in conf:
        build_spec(s, conf[s])

def build_spec(spec, conf):
    branches = conf.get("branches", ["master"])
    if (conf.get("url", False)): return # we'll handle those later
    os.chdir(conf["path"])
    cur_branch = os.popen("git rev-parse --abbrev-ref HEAD").read()
    for branch in branches:
        outdir = os.path.join(conf["output"], spec, branch)
        print BOLD_GREEN + "Processing branch %s of %s (%s)" % (branch, spec, outdir) + NO_COLOUR
        os.system("git checkout %s" % branch)
        publish.main(spec, outdir)
    os.system("git checkout %s" % cur_branch)

def make_index(conf, index_path):
    html = """
    <!DOCTYPE html>
    <html lang='en'>
      <head>
        <meta charset='utf-8'>
        <title>HTML WG</title>
        <link rel='stylesheet' href='http://htmlwg.org/css/htmlwg.css'>
      </head>
      <body>
        <h1>
          <a href="http://w3.org/"><img src="http://www.w3.org/Icons/WWW/w3c_home_nb" alt="W3C"></a>
          HTML WG Drafts
        </h1>
        %s
        <footer><p>Last generated: %s.</p></footer>
      </body>
    </html>
    """
    output = ""
    for spec in conf:
        if conf[spec].get("url", False): continue
        branches = conf[spec].get("branches", ["master"])
        output += "<section><h2>%s</h2><ul>" % conf[spec]["description"]
        for branch in branches:
            output += "<li><a href='%s/%s/Overview.html'>%s</a></li>" % (spec, branch, branch)
        output += "</ul></section>"
    with open(index_path, "w") as data: data.write(html % (output, formatdate()))
    

if __name__ == '__main__':
    try:
        index_path = sys.argv[1]
    except IndexError:
        index_path = None
    main(index_path)
