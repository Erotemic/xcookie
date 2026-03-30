#!/usr/bin/env python3
import scriptconfig as scfg
import ubelt as ub


class MakeNontransitiveLockfileCLI(scfg.DataConfig):
    """
    Given a requirements file the goal of this is to enrich entries with
    minimum versions.

    TODO:
        - handle python specific versions?
        - specific os?

    Notes:
        This command does something similar

        uv pip compile requirements.txt --no-annotate --no-header --no-deps | sed 's|==|>=|g'

    """

    src_files = scfg.Value(None, nargs='+', help='requirement sourcefiles')

    @classmethod
    def main(cls, argv=1, **kwargs):
        """
        Example:
            >>> # xdoctest: +SKIP
            >>> from make_nontransitive_lockfile import *  # NOQA
            >>> argv = 0
            >>> kwargs = dict()
            >>> cls = MakeNontransitiveLockfileCLI
            >>> config = cls(**kwargs)
            >>> cls.main(argv=argv, **config)
        """
        config = cls.cli(argv=argv, data=kwargs, strict=True, verbose='auto')

        if 0:
            config.src_files = ['requirements.txt']

        res = ub.cmd(['uv', 'pip', 'compile', *config.src_files])
        lines = res.stdout.strip().splitlines()
        graph = parse_uv_compile(lines)

        import networkx as nx

        nx.write_network_text(graph)

        top = graph.adj['-r requirements.txt']
        updated_lines = []
        for node in top:
            data = graph.nodes[node]
            version = data['version']
            line = f'{node} >= {version}'
            updated_lines.append(line)

        print('\n'.join(updated_lines))


def parse_uv_compile(lines):
    import re
    import networkx as nx

    graph = nx.DiGraph()

    i = 0
    n = len(lines)

    while i < n:
        line = lines[i].rstrip()

        # Skip comments and empty lines
        if line.startswith('#') or not line.strip():
            i += 1
            continue

        # Match "package==version"
        m = re.match(r'^([a-zA-Z0-9_\-\.]+)==([^\s]+)', line)
        if not m:
            i += 1
            continue

        package = m.group(1)
        version = m.group(2)
        vias = []

        i += 1
        while i < n and lines[i].lstrip().startswith('#'):
            via_line = lines[i].strip().lstrip('#').strip()

            if via_line.startswith('via '):
                via_source = via_line[4:].strip()
                if via_source:
                    vias.append(via_source)
            elif via_line:
                if via_line != 'via':
                    vias.append(via_line)

            i += 1

        graph.add_node(package, version=version, vias=vias)

        for via in vias:
            if via != package:  # avoid self-loops
                graph.add_edge(via, package)

    return graph


__cli__ = MakeNontransitiveLockfileCLI

if __name__ == '__main__':
    """

    CommandLine:
        python ~/code/xcookie/dev/poc/make_nontransitive_lockfile.py
        python -m make_nontransitive_lockfile
    """
    __cli__.main()
