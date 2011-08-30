#!/usr/bin/python
from distutils.core import setup

setup(name="jurt",
        version = "0.01",
        description = "Jurt builds packages like iurt",
        url = "http://wiki.mandriva.com/",
        author = "Bogdano Arendartchuk",
        author_email = "bogdano@mandriva.com",
        license = "GPL",
        long_description = \
"""It builds packages like iurt""",
        packages = [
            "jurtlib/"],
        scripts = ["jurt",
                "jurt-build",
                "jurt-shell",
                "jurt-put",
                "jurt-showrc",
                "jurt-root-command",
                "jurt-setup",
                "jurt-test-sudo",
                "jurt-list-targets",
                "jurt-list-roots",
        ],
        data_files = [
            ('/etc/jurt/',
                ['jurt.conf'] ),
            ('/usr/share/doc/jurt/',
                ['README'])]
    )


