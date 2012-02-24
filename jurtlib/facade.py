#
# Copyright (c) 2011,2012 Bogdano Arendartchuk <bogdano@mandriva.com.br>
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
        self.targets = {}
        self.targetsconf = targetmod.get_targets_conf(config)

    def init_target(self, name):
        self.targetsconf[name] # to raise keyerror
        try:
            target = self.targets[name]
        except KeyError:
            target = targetmod.load_target(name, self.config, self.targetsconf[name])
            self.targets[name] = target
        return target

    def _init_targets(self):
        for name in self.targetsconf:
            self.init_target(name)

    def get_target(self, name=None, id=None, interactive=False):
        if not self.targetsconf:
            raise SetupError, ("no build targets found, see %s" %
                    (self.config.conf.system_file))
        if name is None:
            if id:
                for targetname in self.targetsconf:
                    target = self.init_target(targetname)
                    name = target.rootmanager.guess_target_name(id,
                            interactive)
                    if name:
                        if name == targetname:
                            return target
                        break
            if name is None:
                name = self.config.jurt.default_target
                if name == targetmod.UNSET_DEFAULT_TARGET:
                    if len(self.targetsconf) == 1:
                        name = self.targetsconf.keys()[0]
                    else:
                        raise Error, "no target name provided and "\
                                "no default target set in configuration"
        try:
            target = self.init_target(name)
        except KeyError:
            #FIXME use BuildError
            raise Error, "no such target: %s" % (name)
        target.check_permissions(False)
        return target

    def build(self, paths, targetname=None, id=None, fresh=False,
            stage=None, timeout=None, outputfile=None, keeproot=False,
            keepbuilding=False):
        """Builds a set of packages"""
        target = self.get_target(targetname, id, interactive=bool(stage))
        target.build(paths, id, fresh, stage, timeout, outputfile,
                keeproot, keepbuilding)

    def target_names(self):
        defname = self.config.jurt.default_target
        for name in self.targetsconf.iterkeys():
            yield name, (name == defname)


    def shell(self, targetname=None, id=None, fresh=False):
        target = self.get_target(targetname, id, interactive=True)
        target.shell(id=id, fresh=fresh)

    def list_roots(self):
        self._init_targets()
        targets = self.targets.values()
        if targets:
            for rootinfo in targets[0].list_roots():
                yield rootinfo

    def put(self, paths, targetname, id):
        target = self.get_target(targetname, id, interactive=True)
        target.put(paths, id)

    def pull(self, paths, targetname, id, dest, overwrite=False,
            dryrun=False):
        target = self.get_target(targetname, id, interactive=True)
        for info in target.pull(paths, id, dest, overwrite=overwrite,
                dryrun=dryrun):
            yield info

    def clean(self, dry_run=False):
        self._init_targets()
        for target in self.targets.values():
            for info in target.clean(dry_run):
                yield info

    def keep(self, id):
        target = self.get_target(None, id)
        target.keep(id)

    def invalidate(self, target):
        target = self.get_target(None, None)
        target.invalidate()

    def root_path(self, id, interactive=True):
        target = self.get_target(None, id, interactive)
        return target.root_path(id)

    def check_permissions(self, interactive=True):
        self._init_targets()
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
