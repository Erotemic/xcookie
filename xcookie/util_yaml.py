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
    data = yaml.load(file)
    # Loader=yaml.SafeLoader)
    return data
