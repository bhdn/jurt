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
from jurtlib.configutil import parse_conf_fields
from jurtlib.template import template_expand

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
    def install_build_deps(self, srcpkgpath, root, builduser, homedir, repos,
            logstore, spool):
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
    def files_to_pull(self):
        """Provides a list of globs of PM files that can be pulled from a
        root"""
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
    def __init__(self, configline):
        raise NotImplementedError

class URPMIRepos(Repos):

    use_from_system_line = "use-repositories-from-system"

    def __init__(self, configline, listmediascmd, ignoremediasexpr):
        self.listmediascmd = listmediascmd
        self.ignoremediasexpr = ignoremediasexpr
        if configline.strip() == self.use_from_system_line:
            self._medias = None
        else:
            self._medias = self.parse_conf(configline)

    @classmethod
    def parse_conf(class_, configline):
        medias = []
        for conf in configline.split("|"):
            conf = conf.strip()
            if not conf:
                continue
            fields = shlex.split(conf)
            if len(fields) < 2:
                logger.warn("suspiciously small number of fields in "
                        "urpmi media configuration: %s" % (conf))
                continue
            medias.append(fields)
        return medias

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
        if self._medias is None:
            logger.debug("no medias defined, going to fetch medias "
                    "from system")
            self._medias = self._medias_from_system()
        return self._medias[:]

    def empty(self):
        return not self._medias

def compile_conf_re(value, field):
    try:
        comp = re.compile(value)
    except re.error, e:
        raise PackageManagerError, ("invalid regexp in "
            "configuration option %s: %r: %s" % (field, value, e))
    return comp

def split_extra_macros(rawvalue, field):
    return parse_conf_fields(rawvalue, 2, field)

def parse_replace_expr(rawvalue, field):
    found = parse_conf_fields(rawvalue, 2, field)
    pairs = []
    for rawexpr, repl in found:
        expr = compile_conf_re(rawexpr, field)
        pairs.append((expr, repl))
    return pairs

class RPMBasedPackageManager(PackageManager):

    @classmethod
    def load_config(class_, pmconf, globalconf):
        basepkgs = pmconf.base_packages.split()
        interactivepkgs = pmconf.interactive_packages.split()
        rpmunpackcmd = shlex.split(pmconf.rpm_install_source_command)
        rpmbuildcmd = shlex.split(pmconf.rpm_build_source_command)
        rpmpackagercmd = shlex.split(pmconf.rpm_get_packager_command)
        collectglob = shlex.split(pmconf.rpm_collect_glob)
        genhdlistcmd = shlex.split(pmconf.genhdlist_command)
        rpmarchcmd = shlex.split(pmconf.rpm_get_arch_command)
        rpmtopdir = pmconf.rpm_topdir.strip()
        rpmsubdirs = shlex.split(pmconf.rpm_topdir_subdirs)
        rpmmacros = pmconf.rpm_macros_file.strip()
        defpackager = pmconf.rpm_packager_default.strip()
        packager = pmconf.rpm_packager.strip()
        rpmlistpkgs = shlex.split(pmconf.rpm_list_packages_command)
        allowedrpmcmds = shlex.split(pmconf.interactive_allowed_rpm_commands)
        extramacros = split_extra_macros(pmconf.rpm_build_macros,
                "rpm-build-macros")
        if packager == "undefined":
            packager = None
        filestopull = shlex.split(pmconf.pull_glob)
        rpmbuildreqspec = shlex.split(pmconf.rpm_buildreqs_from_spec_command)
        rpmbuildreqsrpm = shlex.split(pmconf.rpm_buildreqs_from_srpm_command)
        rpmrecreatesrpm = shlex.split(pmconf.rpm_recreate_srpm_command)
        skipdepsex = compile_conf_re(pmconf.rpm_skip_build_deps,
                "rpm-skip-build-deps")
        replacedepsex = parse_replace_expr(pmconf.rpm_replace_build_deps,
                "rpm-replace-build-deps")
        return dict(basepkgs=basepkgs,
                interactivepkgs=interactivepkgs,
                rootsdir=pmconf.roots_path,
                rpmunpackcmd=rpmunpackcmd,
                rpmbuildcmd=rpmbuildcmd,
                collectglob=collectglob,
                genhdlistcmd=genhdlistcmd,
                rpmarchcmd=rpmarchcmd,
                rpmpackagercmd=rpmpackagercmd,
                defpackager=defpackager,
                packager=packager,
                rpmtopdir=rpmtopdir,
                rpmsubdirs=rpmsubdirs,
                rpmmacros=rpmmacros,
                rpmlistpkgs=rpmlistpkgs,
                extramacros=extramacros,
                filestopull=filestopull,
                allowedrpmcmds=allowedrpmcmds,
                rpmbuildreqspec=rpmbuildreqspec,
                rpmbuildreqsrpm=rpmbuildreqsrpm,
                rpmrecreatesrpm=rpmrecreatesrpm,
                skipdepsex=skipdepsex,
                replacedepsex=replacedepsex)

    def __init__(self, rootsdir, rpmunpackcmd, rpmbuildcmd, collectglob,
            rpmarchcmd, rpmpackagercmd, basepkgs, interactivepkgs,
            defpackager, packager, rpmtopdir, rpmsubdirs, rpmmacros,
            rpmlistpkgs, extramacros, filestopull, allowedrpmcmds,
            rpmbuildreqspec, rpmbuildreqsrpm, rpmrecreatesrpm, skipdepsex,
            replacedepsex):
        self.rootsdir = rootsdir
        self.basepkgs = basepkgs
        self.interactivepkgs = interactivepkgs
        self.rpmunpackcmd = rpmunpackcmd
        self.rpmbuildcmd = rpmbuildcmd
        self.collectglob = collectglob
        self.rpmarchcmd = rpmarchcmd
        self.rpmpackagercmd = rpmpackagercmd
        self.defpackager = defpackager
        self.packager = packager
        self.rpmtopdir = rpmtopdir
        self.rpmsubdirs = rpmsubdirs
        self.rpmmacros = rpmmacros
        self.rpmlistpkgs = rpmlistpkgs
        self.extramacros = extramacros
        self.filestopull = filestopull
        self.allowedrpmcmds = allowedrpmcmds
        self.rpmbuildreqspec = rpmbuildreqspec
        self.rpmbuildreqsrpm = rpmbuildreqsrpm
        self.rpmrecreatesrpm = rpmrecreatesrpm
        self.skipdepsex = skipdepsex
        self.replacedepsex = replacedepsex

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

    def check_build_stage(self, stage):
        if stage not in "pcilabstf":
            raise PackageManagerError, ("invalid build stage: %s" %
                    (stage))

    def files_to_pull(self):
        return self.filestopull[:]

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

    def describe_root(self, root, username, logstore):
        args = self.rpmlistpkgs[:]
        outputlogger = logstore.get_output_handler("packages-list")
        try:
            root.su().run_as(args, user=username,
                    outputlogger=outputlogger)
        finally:
            outputlogger.close()

    def fix_build_deps(self, deps):
        newdeps = []
        for dep in deps:
            for expr, repl in self.replacedepsex:
                try:
                    dep = expr.sub(repl, dep)
                except re.error, e:
                    logger.warn("error while replacing build-dep "
                            "string %r: %s", dep, e)
            if self.skipdepsex.match(dep):
                logger.debug("skipping build dep based on config: %s", dep)
                continue
            newdeps.append(dep.strip())
        return newdeps

    def list_build_deps_oldrpm(self, srcpkgpath, root, builduser, homedir,
            outputlogger):
        def list_srpms():
            all = set()
            for baseexpr in self.collectglob:
                expr = os.path.join(homedir, baseexpr)
                all.update(path for path in root.glob(expr)
                                    if path.endswith(".src.rpm"))
            return all
        args = self.rpmrecreatesrpm[:]
        args.append(srcpkgpath)
        before = list_srpms()
        try:
            root.su().run_as(args, user=builduser,
                    outputlogger=outputlogger)
        except su.CommandError, e:
            raise PackageManagerError, ("failed to recreate the "
                    "source package, see the logs at %s" %
                    (outputlogger.location()))
        after = list_srpms()
        args = self.rpmbuildreqsrpm[:]
        args.extend(after.difference(before))
        try:
            output = root.su().run_as(args, user=builduser, quiet=True,
                    ignorestderr=True)
            deps = output.splitlines()
        except su.CommandError, e:
            raise PackageManagerError, ("failed to query build "
                    "dependecies: %s" % (e))
        return deps

    def list_build_deps(self, srcpkgpath, root, builduser, homedir,
            outputlogger):
        args = self.rpmbuildreqspec[:]
        args.append(srcpkgpath)
        try:
            output = root.su().run_as(args, user=builduser, quiet=True)
            deps = output.splitlines()
        except su.CommandError, e:
            if "unknown option" in e.output:
                logger.debug("%r failed with %r, so we will have to "
                        "recreate the srpm and run rpm -qRp", args,
                        e.output)
                deps = self.list_build_deps_oldrpm(srcpkgpath, root,
                        builduser, homedir, outputlogger)
            else:
                raise PackageManagerError, ("failed to query build "
                        "dependencies: %s" % (e))
        return deps

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
                        outputlogger=outputlogger, timeout=timeout,
                        remount=True) # FIXME either remount is at the
                                      # wrong place or it should have
                                      # another name that is more
                                      # meaningful to the caller
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

class URPMIPackageManager(RPMBasedPackageManager):

    @classmethod
    def load_config(class_, pmconf, globalconf):
        names = RPMBasedPackageManager.load_config(pmconf,
                globalconf)
        urpmiopts = shlex.split(pmconf.urpmi_extra_options)
        urpmivalidopts = pmconf.urpmi_valid_options.split()
        addmediacmd = shlex.split(pmconf.urpmiaddmedia_command)
        updatecmd = shlex.split(pmconf.urpmi_update_command)
        urpmicmd = shlex.split(pmconf.urpmi_command)
        allowedpmcmds = shlex.split(pmconf.interactive_allowed_urpmi_commands)
        urpmifatalexpr = compile_conf_re(pmconf.urpmi_fatal_output,
                                         "urpmi-fatal-output")
        ignoremediasexpr = compile_conf_re(pmconf.urpmi_ignore_system_medias,
                                         "urpmi-ignore-system-medias")
        listmediascmd = shlex.split(pmconf.urpmi_list_medias_command)
        names.update(dict(urpmiopts=urpmiopts,
            urpmivalidopts=urpmivalidopts,
            addmediacmd=addmediacmd,
            updatecmd=updatecmd,
            urpmicmd=urpmicmd,
            allowedpmcmds=allowedpmcmds,
            urpmifatalexpr=urpmifatalexpr,
            ignoremediasexpr=ignoremediasexpr,
            listmediascmd=listmediascmd))
        return names

    def __init__(self, urpmicmd, genhdlistcmd, addmediacmd, updatecmd,
            urpmiopts, urpmivalidopts, allowedpmcmds, urpmifatalexpr,
            ignoremediasexpr, listmediascmd, *args, **kwargs):
        super(URPMIPackageManager, self).__init__(*args, **kwargs)
        self.urpmiopts = urpmiopts
        self.urpmivalidopts = urpmivalidopts
        self.urpmicmd = urpmicmd
        self.addmediacmd = addmediacmd
        self.updatecmd = updatecmd
        self.genhdlistcmd = genhdlistcmd
        self.allowedpmcmds = allowedpmcmds
        self.urpmifatalexpr = urpmifatalexpr
        self.ignoremediasexpr = ignoremediasexpr
        self.listmediascmd = listmediascmd

    def repos_from_config(self, configstr):
        return URPMIRepos(configstr, self.listmediascmd,
                self.ignoremediasexpr)

    def create_root(self, suwrapper, repos, path, logger, interactive):
        mediacmds = []
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

    def install_build_deps(self, srcpkgpath, root, builduser, homedir, repos,
            logstore, spool):
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


    def update_repository_metadata(self, path):
        # FIXME filedeps!
        args = self.genhdlistcmd[:]
        args.append(path)
        cmd.run(args)

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
        return self.allowedrpmcmds + self.allowedpmcmds

class SmartRepos(Repos):

    def __init__(self, configline):
        self.configline = configline

    def channelargs(self):
        return [shlex.split(rawargs) for rawargs in self.configline.split("|")]

class SmartPackageManager(RPMBasedPackageManager):

    @classmethod
    def load_config(class_, pmconf, globalconf):
        names = RPMBasedPackageManager.load_config(pmconf,
                globalconf)
        smartcmd = shlex.split(pmconf.smart_command)
        addchannelcmd = shlex.split(pmconf.smart_channel_add_command)
        installcmd = shlex.split(pmconf.smart_install_command)
        updatecmd = shlex.split(pmconf.smart_update_command)
        datadir = pmconf.smart_datadir.strip()
        allowedsmartcmds = shlex.split(pmconf.interactive_allowed_smart_commands)
        spoolchannel = shlex.split(pmconf.smart_spool_channel)
        spoolupdatecmd = shlex.split(pmconf.smart_spool_update_command)
        names.update(dict(smartcmd=smartcmd,
            addchannelcmd=addchannelcmd,
            installcmd=installcmd,
            updatecmd=updatecmd,
            datadir=datadir,
            allowedsmartcmds=allowedsmartcmds,
            spoolchannel=spoolchannel,
            spoolupdatecmd=spoolupdatecmd))
        return names

    def __init__(self, smartcmd, addchannelcmd, installcmd, updatecmd,
            datadir, genhdlistcmd, allowedsmartcmds, spoolchannel,
            spoolupdatecmd, *args, **kwargs):
        super(SmartPackageManager, self).__init__(*args, **kwargs)
        self.smartcmd = smartcmd
        self.addchannelcmd = addchannelcmd
        self.installcmd = installcmd
        self.updatecmd = updatecmd
        self.datadir = datadir
        self.genhdlistcmd = genhdlistcmd
        self.allowedsmartcmds = allowedsmartcmds
        self.spoolchannel = spoolchannel
        self.spoolupdatecmd = spoolupdatecmd

    def repos_from_config(self, configstr):
        return SmartRepos(configstr)

    def _smart_root_options(self, rootpath):
        absdatadir = os.path.abspath(rootpath + "/" + self.datadir)
        return ("--data-dir", absdatadir,
                "-o", "rpm-root=%s" % (rootpath))

    def create_root(self, suwrapper, repos, path, logger, interactive):
        cmds = []
        for args in repos.channelargs():
            cmd = []
            cmd.extend(self._smart_root_options(path))
            cmd.extend(args)
            cmds.append(cmd)
        basecmd = []
        basecmd.extend(self._smart_root_options(path))
        interactivecmd = basecmd[:]
        basecmd.extend(self.basepkgs)
        interactivecmd.extend(self.interactivepkgs)
        updatecmd = self._smart_root_options(path)[:]
        try:
            outputlogger = logger.get_output_handler("chroot-install")
            try:
                for cmd in cmds:
                    suwrapper.run_package_manager("smart.addchannel", cmd,
                            outputlogger=outputlogger)
                suwrapper.run_package_manager("smart.update", updatecmd,
                        outputlogger=outputlogger)
                suwrapper.run_package_manager("smart.install", basecmd,
                        outputlogger=outputlogger)
                if interactive and self.interactivepkgs:
                    outputlogger.write(">>> installing interactive "
                            "packages\n")
                    suwrapper.run_package_manager("smart.install", interactivecmd,
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
                    vars = {"path": rootspool.in_root_path()}
                    args = [template_expand(arg, vars)
                            for arg in self.spoolchannel]
                    root.su().run_package_manager("smart.addchannel", args,
                            outputlogger=outputlogger)
            finally:
                outputlogger.close()
                if spool:
                    rootspool.destroy()
        except su.CommandError, e:
            raise PackageManagerError, ("failed to setup repositories, "
                    "see the logs at %s" % (outputlogger.location))

    def install_build_deps(self, srcpkgpath, root, builduser, homedir, repos,
            logstore, spool):
        rootspool = root.make_spool_reachable(spool)
        outputlogger = logstore.get_output_handler("build-deps-install")
        try:
            deps = self.list_build_deps(srcpkgpath, root, builduser,
                    homedir, outputlogger)
            deps = self.fix_build_deps(deps)
            logger.debug("build deps to be considered: %r", deps)
            if deps:
                try:
                    root.su().run_package_manager("smart.install", deps,
                            outputlogger=outputlogger)
                except su.CommandError, e:
                    raise PackageManagerError, ("failed to install build "
                            "dependencies, see the logs at %s" %
                            (outputlogger.location()))
        finally:
            outputlogger.close()
            rootspool.destroy()

    def install(self, packages, root, repos, logstore, logname=None):
        raise NotImplementedError

    def update_repository_metadata(self, path):
        vars = {"path": path}
        args = [template_expand(arg, vars) for arg in self.spoolupdatecmd[:]]
        cmd.run(args)

    def validate_cmd_args(self, pmtype, args):
        absrootsdir = os.path.abspath(self.rootsdir) + "/"
        for arg in args:
            if "=" in args:
                name, value = arg.split("=", 1)
                if name in ("rpm-root", "data-dir"):
                    absroot = os.path.abspath(value) + "/"
                    if not absroot.startswith(absrootsdir):
                        raise CommandValidationError, "%s should be "\
                                "based on %s" % (opt, absrootsdir)

    def cmd_args(self, pmtype, args):
        if pmtype == "smart.install":
            return self.installcmd[:] + args
        elif pmtype == "smart.addchannel":
            return self.addchannelcmd[:] + args
        elif pmtype == "smart.update":
            return self.updatecmd[:] + args
        else:
            raise PackageManagerError, "invalid package manager"

    def allowed_pm_commands(self):
        return self.allowedrpmcmds + self.allowedsmartcmds

package_managers = Registry("package manager type")
package_managers.register("urpmi", URPMIPackageManager)
package_managers.register("smart+urpmi", SmartPackageManager)

def get_package_manager(pmconf, globalconf):
    klass = package_managers.get_class(pmconf.pm_type)
    instance = klass(**klass.load_config(pmconf, globalconf))
    return instance
