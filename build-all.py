
import os, sys
import config, publish

BOLD_GREEN = "\033[01;32m"
NO_COLOUR = "\033[0m"

# TODO
#   - generate an index page for all

def main(spec):
    conf = config.load_config()
    if spec:
        build_spec(spec, conf[spec])
    else:
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

if __name__ == '__main__':
    try:
        spec = sys.argv[1]
    except IndexError:
        spec = None
    main(spec)
