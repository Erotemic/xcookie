"""
Build the readthedocs yaml file.
"""


def build_readthedocs(self):
    from xcookie.util_yaml import Yaml
    import ubelt as ub

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

        # Build documentation in the docs/ directory with Sphinx
        sphinx:
          configuration: docs/source/conf.py

        # Build documentation with MkDocs
        #mkdocs:
        #  configuration: mkdocs.yml

        # Optionally build your docs in additional formats such as PDF and ePub
        formats: all

        python:
          version: 3.7
          # Optionally set the version of Python and requirements required to
          # build your docs
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

    if 'gdal' in self.tags:
        data['python']['install'].insert(0, {'requirements': 'requirements/gdal.txt'})

    import ruamel
    text = ruamel.yaml.round_trip_dump(data, Dumper=ruamel.yaml.RoundTripDumper)
    return text
