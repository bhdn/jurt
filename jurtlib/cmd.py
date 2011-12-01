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
import os
import subprocess
from jurtlib import Error

class CommandError(Error):
    pass

def run(args, error=False, stderr=False):
    if stderr:
        stderr = subprocess.STDOUT
    else:
        if os.path.exists(os.devnull):
            stderr = open(os.devnull)
        else:
            stderr = None
    proc = subprocess.Popen(args=args, shell=False,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    proc.wait()
    output = proc.stdout.read()
    if proc.returncode != 0 and error:
        cmdline = subprocess.list2cmdline(cmd)
        raise CommandError, ("command failed: %s\n%s\n" %
                (cmdline, output))
    return output, proc.returncode
