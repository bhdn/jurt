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
from jurtlib import Error, SetupError
from jurtlib import config, root, su, target as targetmod

class JurtFacade:

    rootmanager = None

    def __init__(self, config):
        self.config = config
        self.targets = targetmod.load_targets(config)

    def _get_target(self, name=None, id=None, interactive=False):
        if not self.targets:
            raise SetupError, ("no build targets found, see %s" %
                    (self.config.conf.system_file))
        if name is None:
            if id:
                for target in self.targets.itervalues():
                    name = target.rootmanager.guess_target_name(id,
                            interactive)
                    if name:
                        break
            if name is None:
                name = self.config.jurt.default_target
                if name == targetmod.UNSET_DEFAULT_TARGET:
                    raise Error, "no target name provided and "\
                            "no default target set in configuration"
        try:
            target = self.targets[name]
        except KeyError:
            #FIXME use BuildError
            raise Error, "no such target: %s" % (name)
        target.check_permissions(False)
        return target

    def build(self, paths, targetname=None, id=None, fresh=False,
            stage=None, timeout=None, outputfile=None, keeproot=False):
        """Builds a set of packages"""
        target = self._get_target(targetname, id, interactive=bool(stage))
        target.build(paths, id, fresh, stage, timeout, outputfile,
                keeproot)

    def target_names(self):
        return self.targets.keys()

    def shell(self, targetname=None, id=None, fresh=False):
        target = self._get_target(targetname, id, interactive=True)
        target.shell(id=id, fresh=fresh)

    def list_roots(self):
        targets = self.targets.values()
        if targets:
            for rootinfo in targets[0].list_roots():
                yield rootinfo

    def put(self, paths, targetname, id):
        target = self._get_target(targetname, id)
        target.put(paths, id)

    def check_permissions(self, interactive=True):
        if not self.targets:
            raise Error, "no targets setup, you must have at least "\
                    "one setup in configuration for testing"
        try:
            for targetname in self.targets:
                if interactive:
                    yield "testing target %s.." % (targetname)
                self.targets[targetname].check_permissions(interactive)
                if interactive:
                    yield "OK"

        except su.SudoNotSetup:
            raise Error, ("the sudo helper for jurt is not setup, "
                    "please run as root: jurt-setup -u %s" %
                    (su.my_username()[0]))
