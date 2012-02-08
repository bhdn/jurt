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
import sys
import os
import time
import logging
import subprocess
import shlex
import shutil
from jurtlib import CommandError, Error, util
from jurtlib.registry import Registry
from jurtlib.configutil import parse_bool
from jurtlib.spool import Spool
from jurtlib.su import my_username

logger = logging.getLogger("jurt.build")

class BuildError(Error):
    pass

class BuildResult:

    def __init__(self, id, sourceid, package, success, builtpaths):
        self.id = id
        self.sourceid = sourceid
        self.package = package
        self.success = success
        self.builtpaths = builtpaths

def create_dirs(path):
    if not os.path.exists(path):
        logger.debug("created directory %s" % (path))
        os.makedirs(path)

class Builder:

    @classmethod
    def load_config(class_, rootmanager, packagemanager, buildconf,
            globalconf):
        repos = packagemanager.repos_from_config(buildconf.repos)
        interactive = parse_bool(buildconf.interactive)
        deliverydir = os.path.expanduser(buildconf.delivery_dir)
        logcompresscmd = shlex.split(buildconf.log_compress_command)
        try:
            maxuid = int(buildconf.max_uid)
        except ValueError:
            logger.warn(("invalid value for max-uid configuration "
                        "option: %r"), buildconf.max_uid)
        return dict(rootmanager=rootmanager,
                packagemanager=packagemanager,
                repos=repos,
                spooldir=buildconf.spool_dir,
                donedir=buildconf.success_dir,
                faildir=buildconf.failure_dir,
                builtdirname=buildconf.built_dir_name,
                logsdirname=buildconf.logs_dir_name,
                builduser=buildconf.build_user,
                builderhome=buildconf.builder_home,
                useruid=buildconf.builder_uid,
                idtimefmt=buildconf.buildid_timefmt,
                interactive=interactive,
                deliverydir=deliverydir,
                deliverylogext=buildconf.delivery_log_file_ext,
                logcompresscmd=logcompresscmd,
                packagesdirname=buildconf.packages_dir_name,
                latestname=buildconf.latest_home_link_name,
                maxuid=maxuid)

    def __init__(self, rootmanager, packagemanager, repos, spooldir,
            donedir, faildir, builduser, builderhome, useruid, idtimefmt,
            interactive, deliverydir, deliverylogext, logcompresscmd,
            packagesdirname, latestname, maxuid, builtdirname="built",
            logsdirname="logs"):
        self.rootmanager = rootmanager
        self.packagemanager = packagemanager
        self.repos = repos
        self.spooldir = spooldir
        self.donedir = donedir
        self.faildir = faildir
        self.builtdirname = builtdirname
        self.logsdirname = logsdirname
        self.builduser = builduser
        self.useruid = useruid
        self.builderhome = builderhome
        self.idtimefmt = idtimefmt
        self.interactive = interactive
        self.deliverydir = deliverydir
        self.deliverylogext = deliverylogext
        self.logcompresscmd = logcompresscmd
        self.packagesdirname = packagesdirname
        self.latestname = latestname
        self.maxuid = maxuid

    def root_name(self, id, sourceid, sourcepath):
        # FIXME should instead get some package information and build a proper
        # name from it
        return id + "-" + sourceid

    def create_spool(self, name):
        topdir = os.path.join(self.spooldir, name)
        spool = Spool(topdir, self.packagemanager) 
        spool.create_dirs()
        return spool

    def _find_available_uid(self):
        import pwd
        import random
        try:
            used = frozenset(u.pw_uid for u in pwd.getpwall())
        except EnvironmentError, e:
            raise BuildError, ("failed to enumerate users in the "
                    "system: %s" % (e))
        for i in xrange(0, self.maxuid):
            chosen = random.randint(1000, self.maxuid)
            if chosen not in used:
                return chosen
        raise BuildError, "wow, no available free UIDs!"

    # also run as root
    def build_user_info(self):
        if self.interactive:
            return my_username()
        else:
            if self.useruid == "any-available":
                uid = self._find_available_uid()
            else:
                uid = self.useruid
            return self.builduser, uid

    def build_user_home(self, username):
        from jurtlib.template import template_expand
        env = {"username": username}
        value = template_expand(self.builderhome, env)
        path = os.path.abspath(value)
        return path

    def build_one(self, id, fresh, sourceid, path, logstore, spool,
            stage=None, timeout=None, keeproot=False):
        logger.info("working on %s", sourceid)
        root = self._get_root(id, fresh, logstore, self.interactive)
        root.activate()
        try:
            username, uid = self.build_user_info()
            homedir = self.build_user_home(username)
            if fresh:
                root.add_user(username, uid)
                self.packagemanager.setup_repositories(root, self.repos,
                        logstore, spool)
            self.packagemanager.build_prepare(root, homedir, username, uid)
            insidepath = root.copy_in(path, homedir, uid)
            srcpath = self.packagemanager.extract_source(insidepath, root,
                    username, homedir, logstore)
            logger.info("installing build dependencies")
            self.packagemanager.install_build_deps(srcpath, root, username,
                    homedir, self.repos, logstore, spool)
            self.packagemanager.describe_root(root, username, logstore)
            logger.info("building")
            (package, success, builtpaths) = \
                    self.packagemanager.build_source(srcpath, root, logstore,
                            username, homedir, spool, stage, timeout)
            if self.interactive:
                root.interactive_prepare(username, uid,
                        self.packagemanager, self.repos, logstore)
                root.interactive_shell(username)
            if success:
                iddir = os.path.join(self.donedir, id)
            else:
                iddir = os.path.join(self.faildir, id)
            builtdest = os.path.join(iddir, self.builtdirname)
            if not os.path.exists(builtdest):
                logger.debug("created %s" % (builtdest))
                os.makedirs(builtdest)
            if builtpaths:
                root.copy_out(builtpaths, builtdest) # FIXME set ownership
        finally:
            try:
                root.deactivate()
            except:
                sys.stderr.write("\nWARNING WARNING: something bad happened "
                        "while unmouting root, things were possibly left "
                        "mounted!\n")
                raise
        if not keeproot:
            root.destroy(self.interactive)
        localbuilt = []
        localbuilt = [os.path.join(builtdest, os.path.basename(path))
                for path in builtpaths]
        if success:
            spool.put_packages(localbuilt)
        result = BuildResult(id, sourceid, package, success, localbuilt)
        return result

    def _get_source_id(self, sourcepath):
        info = self.packagemanager.get_source_info(sourcepath)
        name = info.name + "-" + info.version + "-" + info.release
        name = name.replace("/", "_")
        return name

    def build_id(self):
        import time
        name, _ = my_username()
        id = time.strftime(self.idtimefmt) + "-" + name
        return id

    def _pipe_through(self, from_, progargs, to):
        fromfile = open(from_)
        tofile = open(to, "w")
        cmdline = subprocess.list2cmdline(progargs)
        logger.debug("piping %s through %s into %s" % (from_, cmdline, to))
        proc = subprocess.Popen(progargs, shell=False, stdin=fromfile,
                stdout=tofile, stderr=subprocess.PIPE)
        proc.wait()
        if proc.returncode != 0:
            raise CommandError(proc.returncode, cmdline,
                    proc.stderr.read())
        tofile.close()
        fromfile.close()

    def deliver(self, id, buildresults, logstore):
        # setting up base delivery directory
        topdir = os.path.join(self.deliverydir, id)
        latestlink = id
        latestpath = os.path.join(self.deliverydir, self.latestname)
        create_dirs(topdir)
        id, subidpaths = logstore.logs()
        # copying and compressing log files
        for subid, path in subidpaths:
            subtop = os.path.join(topdir, subid, self.logsdirname)
            create_dirs(subtop)
            logname = os.path.basename(path) + self.deliverylogext
            destpath = os.path.join(subtop, logname)
            self._pipe_through(path, self.logcompresscmd, destpath)
        # copying (or hardlinking) the built packages
        for result in buildresults:
            for path in result.builtpaths:
                pkgdestdir = os.path.join(topdir, result.sourceid,
                        self.packagesdirname)
                create_dirs(pkgdestdir)
                destpath = os.path.join(pkgdestdir, os.path.basename(path))
                if util.same_partition(pkgdestdir, path):
                    logger.debug("creating hardlink from %s to %s" % (path,
                        destpath))
                    os.link(path, destpath)
                else:
                    logger.debug("copying %s to %s" % (path, destpath))
                    shutil.copy(path, destpath)
        # creating a symlink pointing to the most recently delivered build
        util.replace_link(latestpath, id)
        logger.info("done. see %s" % (topdir))

    def _get_root(self, id, fresh, logstore, interactive):
        if fresh:
            logger.info("creating root %s", id)
            root = self.rootmanager.create_new(id, self.packagemanager,
                    self.repos, logstore, interactive=interactive)
        else:
            logger.info("preparing existing root")
            root = self.rootmanager.get_root_by_name(id,
                    self.packagemanager, interactive=interactive)
        return root

    def build(self, id, fresh, paths, logstore, stage=None, timeout=None,
            keeproot=False):
        spool = self.create_spool(id)
        # TODO ^^^^^ think about unintended spool reuse
        results = []
        for sourcepath in paths:
            self.packagemanager.check_source_package(sourcepath)
        for sourcepath in paths:
            sourceid = self._get_source_id(sourcepath)
            result = self.build_one(id, fresh, sourceid, sourcepath,
                    logstore.subpackage(sourceid), spool, stage, timeout,
                    keeproot)
            results.append(result)
        logstore.done()
        self.deliver(id, results, logstore)
        return results

    def shell(self, id, fresh, logstore):
        root = self._get_root(id, fresh, logstore, interactive=True)
        root.activate()
        try:
            username, uid = self.build_user_info()
            if fresh:
                self.packagemanager.setup_repositories(root, self.repos,
                        logstore)
                root.add_user(username, uid)
                root.interactive_prepare(username, uid, self.packagemanager, self.repos,
                        logstore)
                homedir = self.build_user_home(username)
                self.packagemanager.build_prepare(root, homedir, username, uid)
            root.interactive_shell(username)
        finally:
            root.deactivate()

    def set_interactive(self):
        self.interactive = True

build_types = Registry("builder type")
build_types.register("default", Builder)

def get_builder(rootmanager, packagemanager, buildconf, globalconf):
    klass_ = build_types.get_class(buildconf.build_type)
    instance = klass_(**klass_.load_config(rootmanager, packagemanager,
        buildconf, globalconf))
    return instance
