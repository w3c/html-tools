
import os
import config, publish

# TODO
#   - generate an index page for all
#   - iterate: git checkout, stop on error, publish

def main(spec):
    conf = config.load_config()
    if spec:
        build_spec(spec, conf[spec])
    else:
        for s in conf:
            build_spec(s, conf[s])

def build_spec(spec, conf):
    branches = conf.get("branches", ["master"])
    for branch in branches:
        outdir = os.path.join(conf["output"], spec, branch)
        print "Processing branch %s of %s (%s)" % (branch, spec, outdir)
        # XXX do the git magic here
        publish.main(spec, outdir)

if __name__ == '__main__':
    try:
        spec = sys.argv[1]
    except IndexError:
        spec = None
    main(spec)
