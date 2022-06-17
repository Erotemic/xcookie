
def build_docs_index(self):
    import ubelt as ub
    parts = []
    tags = set(self.config['tags'])
    mod_name = self.config['mod_name']

    if {'gitlab', 'kitware'}.issubset(tags):
        parts.append(ub.codeblock(
            f'''
            :gitlab_url: https://gitlab.kitware.com/computer-vision/{mod_name}
            '''))

    logo_part = ub.codeblock(
        '''
        .. The large version wont work because github strips rst image rescaling. https://i.imgur.com/AcWVroL.png
            # TODO: Add a logo
            .. image:: https://i.imgur.com/PoYIsWE.png
               :height: 100px
               :align: left
        ''')

    parts.append(logo_part)

    title = f"Welcome to {mod_name}'s documentation!"
    underline = '=' * len(title)
    title_part = title + '\n' + underline
    parts.append(title_part)

    init_part = ub.codeblock(
        f'''
        .. The __init__ files contains the top-level documentation overview
        .. automodule:: {mod_name}.__init__
           :show-inheritance:
        ''')
    parts.append(init_part)

    if 0:
        usefulness_part = ub.codeblock(
            '''
            .. # Computed function usefulness
            .. include:: function_usefulness.rst
            ''')
        parts.append(usefulness_part)

    sidebar_part = ub.codeblock(
        f'''
        .. toctree::
           :maxdepth: 5

           {mod_name}


        Indices and tables
        ==================

        * :ref:`genindex`
        * :ref:`modindex`
        ''')
    parts.append(sidebar_part)

    text = '\n\n'.join(parts)
    return text
