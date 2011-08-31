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
import time
import logging
from jurtlib import (Error, SetupError,
        root, config, build, su,
        logger as logstore,
        packagemanager as pm)

logger = logging.getLogger("jurt.target")

UNSET_DEFAULT_TARGET = "undefined"

class PermissionError(SetupError):
    pass

class PermissionChecker:

    def __init__(self, targetconf, globalconf):
        self.targetconf = targetconf
        self.globalconf = globalconf

    def check_filesystem_permissions(self):
        import grp
        grname = self.globalconf.root.jurt_group
        logger.debug("checking if the user is a member of the %s group" %
                (grname))
        try:
            group = grp.getgrnam(grname)
        except KeyError:
            raise SetupError, ("there is no system group '%s', please check "
                    "your jurt installation (and see jurt-setup)" %
                    (grname))
        uname, uid = su.my_username()
        if uname not in group.gr_mem:
            raise PermissionError, ("your user %s should be member of the "
                    "%s group in order to jurt work. Did you run (as root) "
                    "jurt-setup -u %s ?" % (uname, grname, uname))
        if group.gr_gid not in os.getgroups():
            raise PermissionError, ("your user is NOT effectively running as a "
                    "member of the %s group, please restart your session "
                    "before running jurt" % (grname))
        sticky = [self.targetconf.roots_path, self.targetconf.spool_dir,
                self.targetconf.logs_dir, self.targetconf.failure_dir,
                self.targetconf.success_dir]
        for path in sticky:
            logger.debug("checking write permission for %s" % (path))
            if not os.access(path, os.W_OK):
                raise PermissionError, ("%s has no write permission for "
                        "you, please check your jurt installation" %
                        (path))

class Target:

    def __init__(self, name, rootmanager, packagemanager, builder,
            loggerfactory, permchecker):
        self.name = name
        self.rootmanager = rootmanager
        self.packagemanager = packagemanager
        self.builder = builder
        self.loggerfactory = loggerfactory
        self.permchecker = permchecker

    def build(self, paths, id=None, fresh=False, stage=None, timeout=None,
            outputfile=None, keeproot=False):
        if id is None:
            id = self.builder.build_id()
        if stage:
            self.builder.set_interactive()
            self.packagemanager.check_build_stage(stage)
        logstore = self.loggerfactory.get_logger(id, outputfile)
        self.builder.build(id, fresh, paths, logstore, stage, timeout,
                keeproot)

    def shell(self, id=None, fresh=False):
        if id is None:
            id = self.builder.build_id() + "-shell"
        self.builder.set_interactive()
        logstore = self.loggerfactory.get_logger(id)
        self.builder.shell(id, fresh, logstore)

    def put(self, paths, id):
        root = self.rootmanager.get_root_by_name(id, self.packagemanager,
                interactive=True)
        self.builder.set_interactive()
        username, uid = self.builder.build_user_info()
        homedir = self.builder.build_user_home(username)
        for path in paths:
            root.copy_in(path, homedir, sameuser=True)

    def list_roots(self):
        for name in self.rootmanager.list_roots():
            yield name

    def check_permissions(self, interactive=True):
        self.permchecker.check_filesystem_permissions()
        self.rootmanager.test_sudo(interactive)

def load_targets(globalconf):
    targets = {} # { name: Target(), ...}
    for name, targetconf in globalconf.targets():
        loggerfactory = logstore.get_logger_factory(targetconf, globalconf)
        suwrapper = su.get_su_wrapper(name, targetconf, globalconf)
        packagemanager = pm.get_package_manager(targetconf, globalconf)
        rootmanager = root.get_root_manager(suwrapper, targetconf,
                globalconf)
        builder = build.get_builder(rootmanager, packagemanager,
                targetconf, globalconf)
        permchecker = PermissionChecker(targetconf, globalconf)
        target = Target(name, rootmanager, packagemanager, builder,
                loggerfactory, permchecker)
        targets[target.name] = target
    return targets
