import os, json

def rel_to_me (f, origin=__file__):
    return os.path.abspath(os.path.join(os.path.dirname(origin), f))

def load_json (f):
    with open(f) as data: return json.loads(data.read())

def load_config ():
    default_config_file = rel_to_me("default-config.json")
    local_config_file = rel_to_me("local-config.json")
    config = load_json(default_config_file)
    if os.path.exists(local_config_file):
        local_config = load_json(local_config_file)
        for spec in local_config:
            if spec in config:
                for k in local_config[spec]:
                    if k in config[spec] and type(config[spec][k]) is dict:
                        config[spec][k].update(local_config[spec][k])
                    else:
                        config[spec][k] = local_config[spec][k]
            else:
                config[spec] = local_config[spec]
    finger = "<span title='fingerprinting vector' class='fingerprint'><a href='introduction.html#used-to-fingerprint-the-user'><img src='images/fingerprint.png' alt='(This is a fingerprinting vector.)' width=15 height=21></a></span>"
    for spec in config:
        # set fingerprint universally
        if spec == "html":
            config[spec]["vars"]["FINGERPRINT"] = finger
        else:
            config[spec]["vars"]["FINGERPRINT"] = ""
        if config[spec].get("url", False): continue
        if not os.path.isabs(config[spec]["path"]): config[spec]["path"] = rel_to_me(config[spec]["path"], __file__)
        if config[spec].get("output", False):
            if not os.path.isabs(config[spec]["output"]): config[spec]["output"] = rel_to_me(config[spec]["output"], __file__)
        else:
            config[spec]["output"] = os.path.join(config[spec]["path"], "output")
    return config

if __name__ == '__main__':
    import pprint
    pp = pprint.PrettyPrinter(indent=4)
    pp.pprint(load_config())
