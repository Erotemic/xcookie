__doc__="
Xcookie already installs several helper scripts, but it might be nice to handle
them a bit nicer. This note is so I remember the general form of the type
checking command I've been using that works fairly well for getting AI agents
to iterate on the type annotations.
"

ty check {modpath} {testpath} && mypy {modpath} {testpath} --disallow-untyped-defs --disallow-incomplete-defs --disallow-untyped-decorators
ty check {modpath} {testpath} && mypy {modpath} {testpath} --strict


# e.g.
ty check aivm tests && mypy aivm tests --strict
ty check aivm tests && mypy aivm tests --disallow-untyped-defs --disallow-incomplete-defs
