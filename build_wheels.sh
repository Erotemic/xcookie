#!/bin/bash
__doc__="""
SeeAlso:
    pyproject.toml
"""
#pip wheel -w wheelhouse .
python -m build --wheel -o wheelhouse  #  xcookie: +COMMENT_IF(binpy)
#cibuildwheel --config-file pyproject.toml --platform linux --arch x86_64  #  xcookie: +UNCOMMENT_IF(binpy)
