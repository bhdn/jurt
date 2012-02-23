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
"""
Most of the implementation of jurt

In case you want to use jurtlib, see how JurtCommand is implemented on
jurtlib.command. Also take a look at jurtlib.facade.
"""

import logging
log = logging.getLogger("jurt")

class Error(Exception):
    pass

class CommandError(Error):

    def __init__(self, returncode, cmdline, output):
        self.returncode = returncode
        self.cmdline = cmdline
        self.output = output
        msg = ("command failed with exit code "
                "%d\n%s\n%s" % (returncode, cmdline, output))
        self.args = (msg,)


class SetupError(Error):
    """Jurt not properly installed not the system"""
