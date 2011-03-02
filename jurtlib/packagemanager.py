import sys
import os
import shlex
import logging
from jurtlib import Error, CommandError, su, cmd
from jurtlib.registry import Registry

logger = logging.getLogger("jurt.packagemanager")

class PackageManagerError(Error):
    pass

class CommandValidationError(PackageManagerError):
    pass

class PackageManager:

    @classmethod
    def load_config(class_, pmconf, globalconf):
        return dict()

    def create_root(self, root):
        raise NotImplementedError

    def install(self, packages, root):
        raise NotImplementedError

    def install_build_deps(self, sourcepaths, root):
        raise NotImplementedError

    def extract_source(self, path, root):
        raise NotImplementedError

    def build_source(self, sourcepath, root, logger, spool):
        raise NotImplementedError

    @classmethod
    def repos_from_config(self, configstr):
        """Parses a configuration line and converts it to a Repository()"""
        raise NotImplementedError

    def validate_cmd_args(self, args):
        raise NotImplementedError

    def cmd_args(self, args):
        raise NotImplementedError

    def allowed_pm_commands(self):
        raise NotImplementedError

class Repos:

    @classmethod
    def parse_conf(class_, configline):
        raise NotImplementedError

    def empty(self):
        raise NotImplementedError

class URPMIRepos:

    def __init__(self, configline):
        self.medias, self.distribs = self.parse_conf(configline)

    @classmethod
    def parse_conf(class_, configline):
        medias = []
        distribs = []
        for conf in configline.split(";"):
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

    def empty(self):
        return not self.medias and not self.distribs

class URPMIPackageManager(PackageManager):

    @classmethod
    def load_config(class_, pmconf, globalconf):
        basepkgs = pmconf.base_packages.split()
        urpmiopts = shlex.split(pmconf.urpmi_extra_options)
        addmediacmd = shlex.split(pmconf.urpmiaddmedia_command)
        rpmunpackcmd = shlex.split(pmconf.rpm_install_source_command)
        rpmbuildcmd = shlex.split(pmconf.rpm_build_source_command)
        urpmicmd = shlex.split(pmconf.urpmi_command)
        collectglob = shlex.split(pmconf.rpm_collect_glob)
        genhdlistcmd = shlex.split(pmconf.genhdlist_command)
        rpmarchcmd = shlex.split(pmconf.rpm_get_arch_command)
        allowedpmcmds = shlex.split(pmconf.interactive_allowed_urpmi_commands)
        return dict(basepkgs=basepkgs,
                rootsdir=pmconf.roots_path,
                urpmiopts=urpmiopts,
                urpmicmd=urpmicmd,
                addmediacmd=addmediacmd,
                rpmunpackcmd=rpmunpackcmd,
                rpmbuildcmd=rpmbuildcmd,
                collectglob=collectglob,
                genhdlistcmd=genhdlistcmd,
                rpmarchcmd=rpmarchcmd,
                allowedpmcmds=allowedpmcmds)

    def __init__(self, rootsdir, rpmunpackcmd, rpmbuildcmd,
            collectglob, urpmicmd, genhdlistcmd, addmediacmd, rpmarchcmd,
            basepkgs, urpmiopts, allowedpmcmds):
        self.rootsdir = rootsdir
        self.basepkgs = basepkgs
        self.urpmiopts = urpmiopts
        self.urpmicmd = urpmicmd
        self.addmediacmd = addmediacmd
        self.rpmunpackcmd = rpmunpackcmd
        self.rpmbuildcmd = rpmbuildcmd
        self.collectglob = collectglob
        self.genhdlistcmd = genhdlistcmd
        self.rpmarchcmd = rpmarchcmd
        self.allowedpmcmds = allowedpmcmds

    @classmethod
    def repos_from_config(self, configstr):
        return URPMIRepos(configstr)

    def create_root(self, suwrapper, repos, path, logger):
        mediacmds = []
        for distrib in repos.distribs:
            argsmedia = ["--urpmi-root", path]
            argsmedia.extend(("--distrib", distrib))
            mediacmds.append(argsmedia)
        for media in repos.medias:
            argsmedia = ["--urpmi-root", path]
            argsmedia.extend(media)
            mediacmds.append(argsmedia)
        instargs = self.urpmiopts[:]
        instargs.append("--auto")
        instargs.extend(("--root", path))
        instargs.extend(("--urpmi-root", path))
        instargs.extend(self.basepkgs)
        try:
            outputlogger = logger.get_output_handler("chroot-install")
            try:
                for args in mediacmds:
                    suwrapper.run_package_manager("urpmi.addmedia", args,
                            outputlogger=outputlogger)
                suwrapper.run_package_manager("urpmi", instargs,
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
            if spool is not None and spool.package_count():
                args = ["build-spool", rootspool.in_root_path()]
                root.su().run_package_manager("urpmi.addmedia", args,
                        outputlogger=outputlogger)
        finally:
            outputlogger.close()
            if spool:
                rootspool.destroy()

    def install_build_deps(self, srcpkgpath, root, repos, logstore, spool):
        args = self.urpmiopts[:]
        args.append("--auto")
        args.append(srcpkgpath)
        rootspool = root.make_spool_reachable(spool)
        outputlogger = logstore.get_output_handler("build-deps-install")
        try:
            root.su().run_package_manager("urpmi", args,
                    outputlogger=outputlogger)
        finally:
            outputlogger.close()
            rootspool.destroy()

    def install(self, packages, root, repos, logstore, logname=None):
        args = self.urpmiopts[:]
        args.append("--auto")
        args.extend(packages)
        if logname:
            outputlogger = logstore.get_output_handler(logname)
        try:
            try:
                root.su().run_package_manager("urpmi", args,
                        outputlogger=outputlogger)
            finally:
                if logname:
                    outputlogger.close()
        except su.CommandError, e:
            names = " ".join(packages)
            msg = "failed to install packages [%s]" % (names)
            if logname:
                logref = (", detailed error log at: %s" %
                        (outputlogger.location()))
            else:
                logref = ""
            raise PackageManagerError, msg + logref

    def _topdir_args(self, homedir):
        return (("--define", "_topdir %s" % (homedir)))

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

    def check_build_stage(self, stage):
        if stage not in "pcilabstf":
            raise PackageManagerError, ("invalid build stage: %s" %
                    (stage))

    def build_source(self, sourcepath, root, logstore, builduser, homedir,
            spool, stage=None):
        args = self.rpmbuildcmd[:]
        args.extend(self._topdir_args(homedir))
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
                        outputlogger=outputlogger)
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
        opts, args = getopt.gnu_getopt(args, "", ["root=", "auto",
                    "no-suggests", "excludedocs", "auto-select",
                    "proxy=", "use-distrib=", "urpmi-root=", "distrib="])
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
        else:
            raise PackageManagerError, "invalid package manager"

    # run as root
    def allowed_pm_commands(self):
        return self.allowedpmcmds[:]

package_managers = Registry()
package_managers.register("urpmi", URPMIPackageManager)

def get_package_manager(pmconf, globalconf):
    klass = package_managers.get_class(pmconf.pm_type)
    instance = klass(**klass.load_config(pmconf, globalconf))
    return instance
