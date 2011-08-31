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
import subprocess
import logging
from jurtlib import Error

logger = logging.getLogger("jurt.rpmpackage")

class CommandError(Error):
    pass

class RPMPackageError(Error):
    pass

class RPMPackage:

    def __init__(self, path):
        self._loadtags(path)

    def _loadtags(self, path):
        tags = ("name", "epoch", "version", "release", "distepoch",
                "disttag", "arch")
        queryformat = "/".join("%%{%s}" % tag for tag in tags)
        out = self._rpmq(path, queryformat)
        lines = out.split("\n", 1)
        if not lines or not lines[0]:
            raise RPMPackageError, "%s does not seem to be a RPM package" % (path)
        fields = lines[0].split("/")
        err = RPMPackageError("no lines from the RPM output: %s" % (out))
        if len(fields) < len(tags):
            raise err
        def g(it):
            val = it.next()
            if val == "(none)":
                return None
            return val
        it = iter(fields)
        self.name = g(it)
        self.epoch = g(it)
        self.version = g(it)
        self.release = g(it)
        self.distepoch = g(it)
        self.disttag = g(it)
        self.arch = g(it)

    def _rpmq(self, path, qf):
        args = ["/bin/rpm", "-q", "-p", "--qf"]
        args.append(qf)
        args.append(path)
        cmdline = subprocess.list2cmdline(args)
        logger.debug("running %s" % (cmdline))
        proc = subprocess.Popen(args=args, shell=False,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        proc.wait()
        if proc.returncode != 0:
            errorout = proc.stderr.read()
            cmdline = subprocess.list2cmdline(args)
            raise CommandError, ("rpm failed with %d\n%s\n%s" %
                    (proc.returncode, cmdline, errorout))
        return proc.stdout.read()
