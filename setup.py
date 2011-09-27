#!/usr/bin/python
#
# Copyright (c) 2011 Bogdano Arendartchuk <bogdano@mandriva.com.br>
#
# Written by Bogdano Arendartchuk <bogdano@mandriva.com.br>
#
# This file is part of Jurt Build Bot.
#
# Jurt Build Bot is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as published
# by the Free Software Foundation; either version 2 of the License, or (at
# your option) any later version.
#
# Jurt Build Bot is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Jurt Build Bot; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
from distutils.core import setup

setup(name="jurt",
        version = "0.02",
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
                ['README', 'LICENSE']),
            ("share/man/man1/", ["jurt.1"])]
    )


