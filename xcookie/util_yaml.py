import yaml
import io


def yaml_dumps(data):
    def str_presenter(dumper, data):
        # https://stackoverflow.com/questions/8640959/how-can-i-control-what-scalar-form-pyyaml-uses-for-my-data
        if len(data.splitlines()) > 1 or '\n' in data:
            text_list = [line.rstrip() for line in data.splitlines()]
            fixed_data = '\n'.join(text_list)
            return dumper.represent_scalar('tag:yaml.org,2002:str', fixed_data, style='|')
        return dumper.represent_scalar('tag:yaml.org,2002:str', data)

    yaml.add_representer(str, str_presenter)
    # dumper = yaml.dumper.Dumper
    # dumper = yaml.SafeDumper(sort_keys=False)
    # yaml.dump(data, s, Dumper=yaml.SafeDumper, sort_keys=False, width=float("inf"))
    s = io.StringIO()
    # yaml.dump(data, s, sort_keys=False)
    yaml.dump(data, s, Dumper=yaml.Dumper, sort_keys=False, width=float("inf"))
    s.seek(0)
    text = s.read()
    return text


def yaml_loads(text):
    file = io.StringIO(text)
    # data = yaml.load(file, Loader=yaml.SafeLoader)
    import ruamel.yaml
    data = ruamel.yaml.load(file, Loader=ruamel.yaml.RoundTripLoader, preserve_quotes=True)
    return data


def _dev():
    # import yaml
    # yaml
    # https://stackoverflow.com/questions/18065427/generating-anchors-with-pyyaml-dump/36295979#36295979
    from xcookie import rc
    import ubelt as ub
    import yaml
    fpath = rc.resource_fpath('gitlab-ci.purepy.yml.in')
    data = yaml.load(open(fpath, 'r'))
    print('data = {}'.format(ub.repr2(data, nl=-1)))
    from xcookie import util_yaml
    print(util_yaml.yaml_dumps(data))

    import ruamel.yaml
    data = ruamel.yaml.load(open(fpath, 'r'), Loader=ruamel.yaml.RoundTripLoader, preserve_quotes=True)
    print(ruamel.yaml.round_trip_dump(data, Dumper=ruamel.yaml.RoundTripDumper))
