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
import abc
import sys
import os
import shlex
import re
import logging
import tempfile
from jurtlib import Error, CommandError, su, cmd
from jurtlib.registry import Registry

logger = logging.getLogger("jurt.packagemanager")

class PackageManagerError(Error):
    pass

class CommandValidationError(PackageManagerError):
    pass

class PackageManager(object):
    __metaclass__ = abc.ABCMeta

    @classmethod
    @abc.abstractmethod
    def load_config(class_, pmconf, globalconf):
        return dict()

    @abc.abstractmethod
    def create_root(self, root):
        raise NotImplementedError

    @abc.abstractmethod
    def install(self, packages, root):
        raise NotImplementedError

    @abc.abstractmethod
    def install_build_deps(self, sourcepaths, root):
        raise NotImplementedError

    @abc.abstractmethod
    def describe_root(self, root, username, logstore):
        raise NotImplementedError

    @abc.abstractmethod
    def extract_source(self, path, root):
        raise NotImplementedError

    @abc.abstractmethod
    def build_prepare(self, root, homedir, username, uid):
        raise NotImplementedError

    @abc.abstractmethod
    def build_source(self, sourcepath, root, logger, spool):
        raise NotImplementedError

    @abc.abstractmethod
    def repos_from_config(self, configstr):
        """Parses a configuration line and converts it to a Repository()"""
        raise NotImplementedError

    @abc.abstractmethod
    def validate_cmd_args(self, args):
        raise NotImplementedError

    @abc.abstractmethod
    def cmd_args(self, args):
        raise NotImplementedError

    @abc.abstractmethod
    def allowed_pm_commands(self):
        raise NotImplementedError

class Repos(object):
    __metaclass__ = abc.ABCMeta

    use_from_system_line = "use-repositories-from-system"

    @abc.abstractmethod
    def __init__(self, configline):
        raise NotImplementedError

    @classmethod
    @abc.abstractmethod
    def parse_conf(class_, configline):
        raise NotImplementedError

    @abc.abstractmethod
    def empty(self):
        raise NotImplementedError

class URPMIRepos(Repos):

    def __init__(self, configline, listmediascmd, ignoremediasexpr):
        self.listmediascmd = listmediascmd
        self.ignoremediasexpr = ignoremediasexpr
        if configline.strip() == self.use_from_system_line:
            self._medias = self._distribs = None
        else:
            self._medias, self._distribs = self.parse_conf(configline)

    @classmethod
    def parse_conf(class_, configline):
        medias = []
        distribs = []
        for conf in configline.split("|"):
            conf = conf.strip()
            if not conf:
                continue
            fields = conf.split(None, 1)
            if len(fields) < 2:
                logger.warn("suspiciously small number of fields in "
                        "urpmi media configuration: %s" % (conf))
                continue
            elif fields[0] == "--distrib":
                distribs.append(fields[1])
            else:
                medias.append(fields)
        return medias, distribs

    def _medias_from_system(self):
        try:
            logger.debug("running %s", self.listmediascmd)
            output, _ = cmd.run(self.listmediascmd)
        except CommandError, e:
            raise PackageManagerError, ("failed to discover repository "
                    "information from the system: %s" % (e))
        found = []
        for line in output.splitlines():
            if self.ignoremediasexpr.search(line):
                logger.debug("ignoring media line based on "
                        "configuration: %r", line)
                continue
            mediainfo = shlex.split(line)
            logger.debug("system media: %r", mediainfo)
            found.append(mediainfo)
        return found

    def medias(self):
        # as we can't easily figure 'distribs' used in our system, we are
        # going to assume only medias can be fetched
        if self._medias is None and self._distribs is None:
            logger.debug("no medias defined, going to fetch medias "
                    "from system")
            self._medias = self._medias_from_system()
            self._distribs = []
        return self._medias[:]

    def distribs(self):
        if self._distribs is None:
            self.medias()
        return self._distribs[:]

    def empty(self):
        return not self._medias and not self._distribs

def compile_conf_re(value, field):
    try:
        comp = re.compile(value)
    except re.error, e:
        raise PackageManagerError, ("invalid regexp in "
            "configuration option %s: %r: %s" % (field, value, e))
    return comp

def split_extra_macros(value, field):
    found = []
    for rawpair in value.split("|"):
        fields = rawpair.split(None, 1)
        if not fields:
            continue
        if len(fields) != 2:
            raise PackageManagerError, ("the field %s expects "
                    "a macro name and a value: %r" % (field, rawpair))
        found.append(fields)
    return found

class URPMIPackageManager(PackageManager):

    @classmethod
    def load_config(class_, pmconf, globalconf):
        basepkgs = pmconf.base_packages.split()
        interactivepkgs = pmconf.interactive_packages.split()
        urpmiopts = shlex.split(pmconf.urpmi_extra_options)
        urpmivalidopts = pmconf.urpmi_valid_options.split()
        addmediacmd = shlex.split(pmconf.urpmiaddmedia_command)
        updatecmd = shlex.split(pmconf.urpmi_update_command)
        rpmunpackcmd = shlex.split(pmconf.rpm_install_source_command)
        rpmbuildcmd = shlex.split(pmconf.rpm_build_source_command)
        rpmpackagercmd = shlex.split(pmconf.rpm_get_packager_command)
        urpmicmd = shlex.split(pmconf.urpmi_command)
        collectglob = shlex.split(pmconf.rpm_collect_glob)
        genhdlistcmd = shlex.split(pmconf.genhdlist_command)
        rpmarchcmd = shlex.split(pmconf.rpm_get_arch_command)
        allowedpmcmds = shlex.split(pmconf.interactive_allowed_urpmi_commands)
        rpmtopdir = pmconf.rpm_topdir.strip()
        rpmsubdirs = shlex.split(pmconf.rpm_topdir_subdirs)
        rpmmacros = pmconf.rpm_macros_file.strip()
        defpackager = pmconf.rpm_packager_default.strip()
        packager = pmconf.rpm_packager.strip()
        rpmlistpkgs = shlex.split(pmconf.rpm_list_packages_command)
        urpmifatalexpr = compile_conf_re(pmconf.urpmi_fatal_output,
                                         "urpmi-fatal-output")
        ignoremediasexpr = compile_conf_re(pmconf.urpmi_ignore_system_medias,
                                         "urpmi-ignore-system-medias")
        listmediascmd = shlex.split(pmconf.urpmi_list_medias_command)
        extramacros = split_extra_macros(pmconf.rpm_build_macros,
                "rpm-build-macros")
        if packager == "undefined":
            packager = None
        return dict(basepkgs=basepkgs,
                interactivepkgs=interactivepkgs,
                rootsdir=pmconf.roots_path,
                urpmiopts=urpmiopts,
                urpmivalidopts=urpmivalidopts,
                urpmicmd=urpmicmd,
                addmediacmd=addmediacmd,
                updatecmd=updatecmd,
                rpmunpackcmd=rpmunpackcmd,
                rpmbuildcmd=rpmbuildcmd,
                collectglob=collectglob,
                genhdlistcmd=genhdlistcmd,
                rpmarchcmd=rpmarchcmd,
                rpmpackagercmd=rpmpackagercmd,
                allowedpmcmds=allowedpmcmds,
                defpackager=defpackager,
                packager=packager,
                rpmtopdir=rpmtopdir,
                rpmsubdirs=rpmsubdirs,
                rpmmacros=rpmmacros,
                rpmlistpkgs=rpmlistpkgs,
                urpmifatalexpr=urpmifatalexpr,
                ignoremediasexpr=ignoremediasexpr,
                listmediascmd=listmediascmd,
                extramacros=extramacros)

    def __init__(self, rootsdir, rpmunpackcmd, rpmbuildcmd, collectglob,
            urpmicmd, genhdlistcmd, addmediacmd, updatecmd, rpmarchcmd,
            rpmpackagercmd, basepkgs, interactivepkgs, urpmiopts,
            urpmivalidopts, allowedpmcmds, defpackager, packager,
            rpmtopdir, rpmsubdirs, rpmmacros, rpmlistpkgs, urpmifatalexpr,
            ignoremediasexpr, listmediascmd, extramacros):
        self.rootsdir = rootsdir
        self.basepkgs = basepkgs
        self.interactivepkgs = interactivepkgs
        self.urpmiopts = urpmiopts
        self.urpmivalidopts = urpmivalidopts
        self.urpmicmd = urpmicmd
        self.addmediacmd = addmediacmd
        self.updatecmd = updatecmd
        self.rpmunpackcmd = rpmunpackcmd
        self.rpmbuildcmd = rpmbuildcmd
        self.collectglob = collectglob
        self.genhdlistcmd = genhdlistcmd
        self.rpmarchcmd = rpmarchcmd
        self.rpmpackagercmd = rpmpackagercmd
        self.allowedpmcmds = allowedpmcmds
        self.defpackager = defpackager
        self.packager = packager
        self.rpmtopdir = rpmtopdir
        self.rpmsubdirs = rpmsubdirs
        self.rpmmacros = rpmmacros
        self.rpmlistpkgs = rpmlistpkgs
        self.urpmifatalexpr = urpmifatalexpr
        self.ignoremediasexpr = ignoremediasexpr
        self.listmediascmd = listmediascmd
        self.extramacros = extramacros

    def repos_from_config(self, configstr):
        return URPMIRepos(configstr, self.listmediascmd,
                self.ignoremediasexpr)

    def create_root(self, suwrapper, repos, path, logger, interactive):
        mediacmds = []
        for distrib in repos.distribs():
            argsmedia = ["--urpmi-root", path]
            argsmedia.extend(("--distrib", distrib))
            mediacmds.append(argsmedia)
        for media in repos.medias():
            argsmedia = ["--urpmi-root", path]
            argsmedia.extend(media)
            mediacmds.append(argsmedia)
        baseargs = self.urpmiopts[:]
        baseargs.append("--auto")
        baseargs.extend(("--root", path))
        baseargs.extend(("--urpmi-root", path))
        interactiveargs = baseargs[:]
        baseargs.extend(self.basepkgs)
        interactiveargs.extend(self.interactivepkgs)
        try:
            outputlogger = logger.get_output_handler("chroot-install")
            try:
                for args in mediacmds:
                    suwrapper.run_package_manager("urpmi.addmedia", args,
                            outputlogger=outputlogger)
                suwrapper.run_package_manager("urpmi", baseargs,
                        outputlogger=outputlogger)
                if interactive and self.interactivepkgs:
                    outputlogger.write(">>>> installing interactive "
                            "packages\n")
                    suwrapper.run_package_manager("urpmi", interactiveargs,
                            outputlogger=outputlogger)
            finally:
                outputlogger.close()
        except su.CommandError, e:
            raise PackageManagerError, ("failed to create the base root "
                    "installation, detailed error log at: %s" %
                    (outputlogger.location()))

    def setup_repositories(self, root, repos, logstore, spool=None):
        if spool:
            rootspool = root.make_spool_reachable(spool)
        outputlogger = logstore.get_output_handler("addmedia")
        try:
            try:
                if spool is not None and spool.package_count():
                    args = ["build-spool", rootspool.in_root_path()]
                    root.su().run_package_manager("urpmi.addmedia", args,
                            outputlogger=outputlogger)
            finally:
                outputlogger.close()
                if spool:
                    rootspool.destroy()
        except su.CommandError, e:
            raise PackageManagerError, ("failed to setup repositories, "
                    "see the logs at %s" % (outputlogger.location))

    def install_build_deps(self, srcpkgpath, root, repos, logstore, spool):
        args = self.urpmiopts[:]
        args.append("--auto")
        args.append("--buildrequires")
        args.append(srcpkgpath)
        rootspool = root.make_spool_reachable(spool)
        outputlogger = logstore.get_output_handler("build-deps-install",
                trap=self.urpmifatalexpr)
        errmsg = ("failed to install build dependencies, see the logs at %s" %
                    (outputlogger.location()))
        try:
            try:
                root.su().run_package_manager("urpmi.update", [],
                        outputlogger=outputlogger)
                root.su().run_package_manager("urpmi", args,
                        outputlogger=outputlogger)
                if outputlogger.matches:
                    raise PackageManagerError, errmsg
            finally:
                outputlogger.close()
                rootspool.destroy()
        except su.CommandError, e:
            raise PackageManagerError, errmsg

    def describe_root(self, root, username, logstore):
        args = self.rpmlistpkgs[:]
        outputlogger = logstore.get_output_handler("packages-list")
        try:
            root.su().run_as(args, user=username,
                    outputlogger=outputlogger)
        finally:
            outputlogger.close()

    def install(self, packages, root, repos, logstore, logname=None):
        args = self.urpmiopts[:]
        args.append("--auto")
        args.extend(packages)
        if logname:
            outputlogger = logstore.get_output_handler(logname,
                    trap=self.urpmifatalexpr)
            names = " ".join(packages)
            msg = "failed to install packages [%s]" % (names)
            if logname:
                logref = (", detailed error log at: %s" %
                        (outputlogger.location()))
            else:
                logref = ""
        try:
            try:
                root.su().run_package_manager("urpmi.update", [],
                        outputlogger=outputlogger)
                root.su().run_package_manager("urpmi", args,
                        outputlogger=outputlogger)
                if outputlogger.matches:
                    raise PackageManagerError, msg + logref
            finally:
                if logname:
                    outputlogger.close()
        except su.CommandError, e:
            raise PackageManagerError, msg + logref

    def _expand_home(self, str, homedir):
        return str.replace("~", homedir)

    def _topdir(self, homedir):
        return self._expand_home(self.rpmtopdir, homedir)

    def _topdir_args(self, homedir):
        return ("--define", "_topdir %s" % (self._topdir(homedir)))

    def _extra_macros(self):
        for name, value in self.extramacros:
            yield "--define"
            yield "%s %s" % (name, value)

    def extract_source(self, path, root, username, homedir, logstore):
        args = self.rpmunpackcmd[:]
        args.extend(self._topdir_args(homedir))
        args.append(path)
        outputlogger = logstore.get_output_handler("extractsource")
        try:
            try:
                root.su().run_as(args, user=username,
                        outputlogger=outputlogger)
            finally:
                outputlogger.close()
        except su.CommandError:
            raise PackageManagerError, "failed to install the source "\
                    "package, error log at: %s" % (outputlogger.location())
        globexpr = os.path.abspath(homedir + "/SPECS/*.spec")
        found = root.glob(globexpr)
        if not found:
            raise PackageManagerError, "failed to extract %s, no spec "\
                    "files found" % (root.external_path(path))
        return found[0]

    def _get_packager(self):
        packager = self.packager
        if packager is None:
            args = self.rpmpackagercmd[:]
            try:
                output, _ = cmd.run(args)
            except cmd.CommandError, e:
                logger.error("error while getting packager macro: %s" % (e))
                packager = self.defpackager
            else:
                if "PACKAGER_UNDEFINED" in output:
                    packager = self.defpackager
                else:
                    packager = output.strip()
        return packager

    def build_prepare(self, root, homedir, username, uid):
        topdir = self._topdir(homedir)
        dirs = [topdir]
        dirs.extend((os.path.join(topdir, name)
                        for name in self.rpmsubdirs))
        logger.debug("creating RPM build directories on %s: %s",
                topdir, " ".join(self.rpmsubdirs))
        root.mkdir(dirs, uid=uid)
        packager = self._get_packager()
        logger.debug("using %s as packager" % (packager))
        tf = tempfile.NamedTemporaryFile()
        tf.write("""\
%%_topdir %s
%%packager %s
""" % (topdir, packager))
        tf.flush()
        rpmmacros = self._expand_home(self.rpmmacros, homedir)
        logger.debug("writing RPM macros to %s" % (rpmmacros))
        root.copy_in(tf.name, rpmmacros, uid=uid)

    def check_build_stage(self, stage):
        if stage not in "pcilabstf":
            raise PackageManagerError, ("invalid build stage: %s" %
                    (stage))

    def build_source(self, sourcepath, root, logstore, builduser, homedir,
            spool, stage=None, timeout=None):
        args = self.rpmbuildcmd[:]
        args.extend(self._topdir_args(homedir))
        args.extend(self._extra_macros())
        if stage:
            self.check_build_stage(stage)
            args.append("-b" + stage)
        else:
            args.append("-ba")
        args.append(sourcepath)
        success = False
        outputlogger = logstore.get_output_handler("build")
        try:
            try:
                root.su().run_as(args, user=builduser,
                        outputlogger=outputlogger, timeout=timeout)
            except su.CommandError:
                logger.error("build failed, see the logs at %s" %
                        (outputlogger.location()))
            except su.CommandTimeout:
                outputlogger.write("===== timeout\n")
                logger.error("build timed out")
            else:
                success = True
        finally:
            outputlogger.close()
        found = []
        if success:
            for basexpr in self.collectglob:
                globexpr = os.path.join(homedir, basexpr)
                found.extend(root.glob(globexpr))
        return None, success, found

    def update_repository_metadata(self, path):
        # FIXME filedeps!
        args = self.genhdlistcmd[:]
        args.append(path)
        cmd.run(args)

    def get_source_info(self, path):
        from jurtlib.rpmpackage import RPMPackage
        return RPMPackage(path)

    def check_source_package(self, path):
        self.get_source_info(path)

    def system_arch(self):
        output, _ = cmd.run(self.rpmarchcmd)
        return output.strip()

    def valid_binary(self, path):
        if not path.endswith(".rpm") or path.endswith(".src.rpm"):
            return False
        return True

    # executed as root:
    def validate_cmd_args(self, pmtype, args):
        import getopt
        if pmtype == "urpmi" and not "--auto" in args:
            raise CommandValidationError, "--auto is missing in urpmi "\
                    "command line"
        opts, args = getopt.gnu_getopt(args, "", self.urpmivalidopts)
        absrootsdir = os.path.abspath(self.rootsdir) + "/"
        for opt, value in opts:
            if opt == "--root" or opt == "--urpmi-root":
                absroot = os.path.abspath(value) + "/"
                if not absroot.startswith(absrootsdir):
                    raise CommandValidationError, "%s should be "\
                            "based on %s" % (opt, absrootsdir)

    # run as root
    def cmd_args(self, pmtype, args):
        if pmtype == "urpmi":
            return self.urpmicmd[:] + args
        elif pmtype == "urpmi.addmedia":
            return self.addmediacmd[:] + args
        elif pmtype == "urpmi.update":
            return self.updatecmd[:] + args
        else:
            raise PackageManagerError, "invalid package manager"

    # run as root
    def allowed_pm_commands(self):
        return self.allowedpmcmds[:]

package_managers = Registry("package manager type")
package_managers.register("urpmi", URPMIPackageManager)

def get_package_manager(pmconf, globalconf):
    klass = package_managers.get_class(pmconf.pm_type)
    instance = klass(**klass.load_config(pmconf, globalconf))
    return instance
