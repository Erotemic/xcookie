"""
Build the readthedocs yaml file.
"""


def build_readthedocs(self):
    from xcookie.util_yaml import Yaml
    import ubelt as ub

    # https://docs.readthedocs.io/en/stable/config-file/v2.html#build

    default_data = Yaml.loads(ub.codeblock(
        f'''
        # .readthedocs.yml
        # Read the Docs configuration file
        # See https://docs.readthedocs.io/en/stable/config-file/v2.html for details
        #
        # See Also:
        # https://readthedocs.org/dashboard/{self.repo_name}/advanced/

        # Required
        version: 2

        build:
          os: "ubuntu-22.04"
          tools:
            python: "3.11"

        # Build documentation in the docs/ directory with Sphinx
        sphinx:
          configuration: docs/source/conf.py

        # Build documentation with MkDocs
        #mkdocs:
        #  configuration: mkdocs.yml

        # Optionally build your docs in additional formats such as PDF and ePub
        formats: all

        python:
          install:
            - requirements: requirements/docs.txt
            - method: pip
              path: .
              #extra_requirements:
              #  - docs

        #conda:
        #  environment: environment.yml
        '''))

    data = default_data.copy()

    if 'cv2' in self.tags:
        data['python']['install'].insert(0, {'requirements': 'requirements/headless.txt'})
    # else:
    #     if self.config.render_doc_images:
    #         data['python']['install'].insert(0, {'requirements': 'requirements/special-headless.txt'})

    if 'gdal' in self.tags:
        data['python']['install'].insert(0, {'requirements': 'requirements/gdal.txt'})

    import ruamel
    text = ruamel.yaml.round_trip_dump(data, Dumper=ruamel.yaml.RoundTripDumper)
    return text
