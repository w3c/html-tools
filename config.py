import os, json

def rel_to_me (f):
    return os.path.join(os.path.dirname(__file__), f)

def load_json (f):
    with open(f) as data: return json.loads(data.read())

def load_config ():
    default_config_file = rel_to_me("default-config.json")
    local_config_file = rel_to_me("local-config.json")
    config = load_json(default_config_file)
    if os.path.exists(local_config_file):
        local_config = load_json(local_config_file)
        for k in local_config.keys():
            if k in config:
                config[k].update(local_config[k])
            else:
                config[k] = local_config[k]
    return config

if __name__ == '__main__':
    import pprint
    pp = pprint.PrettyPrinter(indent=4)
    pp.pprint(load_config())
