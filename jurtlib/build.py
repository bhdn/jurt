import sys
import os
import time
import logging
import subprocess
import shlex
import shutil
from jurtlib import CommandError, util
from jurtlib.registry import Registry
from jurtlib.config import parse_bool
from jurtlib.spool import Spool
from jurtlib.su import my_username

logger = logging.getLogger("jurt.build")

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

def same_partion(one, other):
    st_one = os.stat(one)
    st_other = os.stat(other)
    return st_one.st_dev == st_other.st_dev

class Builder:

    @classmethod
    def load_config(class_, rootmanager, packagemanager, buildconf,
            globalconf):
        repos = packagemanager.repos_from_config(buildconf.repos)
        if repos.empty():
            logger.warn("no valid repository entries found for target "
                    "%s" % (buildconf.target_name))
        interactive = parse_bool(buildconf.interactive)
        deliverydir = os.path.expanduser(buildconf.delivery_dir)
        logcompresscmd = shlex.split(buildconf.log_compress_command)
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
                latestname=buildconf.latest_link_name)

    def __init__(self, rootmanager, packagemanager, repos, spooldir,
            donedir, faildir, builduser, builderhome, useruid, idtimefmt,
            interactive, deliverydir, deliverylogext, logcompresscmd,
            packagesdirname, latestname, builtdirname="built",
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

    def root_name(self, id, sourceid, sourcepath):
        # FIXME should instead get some package information and build a proper
        # name from it
        return id + "-" + sourceid

    def create_spool(self, name):
        topdir = os.path.join(self.spooldir, name)
        spool = Spool(topdir, self.packagemanager) 
        spool.create_dirs()
        return spool

    # also run as root
    def build_user_info(self):
        if self.interactive:
            return my_username()
        else:
            return self.builduser, self.useruid

    def build_user_home(self, username):
        from jurtlib.template import template_expand
        env = {"username": username}
        value = template_expand(self.builderhome, env)
        path = os.path.abspath(value)
        return path

    def build_one(self, id, sourceid, path, logstore, spool, stage=None):
        root = self.rootmanager.create_new(self.root_name(id, sourceid, path),
                self.packagemanager, self.repos, logstore)
        root.mount()
        try:
            username, uid = self.build_user_info()
            homedir = self.build_user_home(username)
            root.add_user(username, uid)
            insidepath = root.copy_in(path, homedir, self.useruid)
            srcpath = self.packagemanager.extract_source(insidepath, root,
                    username, homedir, logstore)
            self.packagemanager.setup_repositories(root, self.repos,
                    logstore, spool)
            self.packagemanager.install_build_deps(insidepath, root, self.repos,
                    logstore, spool)
            (package, success, builtpaths) = \
                    self.packagemanager.build_source(srcpath, root, logstore,
                            username, homedir, spool, stage)
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
            root.copy_out(builtpaths, builtdest) # FIXME set ownership
        finally:
            try:
                root.umount()
            except:
                sys.stderr.write("\nWARNING WARNING: something bad happened "
                        "while unmouting root, things were possibly left "
                        "mounted!\n")
                raise
        localbuilt = []
        localbuilt = [os.path.join(builtdest, os.path.basename(path))
                for path in builtpaths]
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
                if same_partion(pkgdestdir, path):
                    logger.debug("creating hardlink from %s to %s" % (path,
                        destpath))
                    os.link(path, destpath)
                else:
                    logger.debug("copying %s to %s" % (path, destpath))
                    shutil.copy(path, destpath)
        # creating a symlink pointing to the most recently delivered build
        util.replace_link(latestpath, id)
        logger.info("done. check out %s" % (topdir))

    def build(self, id, paths, logstore, stage=None):
        spool = self.create_spool(id)
        results = []
        for sourcepath in paths:
            self.packagemanager.check_source_package(sourcepath)
        for sourcepath in paths:
            sourceid = self._get_source_id(sourcepath)
            result = self.build_one(id, sourceid, sourcepath,
                    logstore.subpackage(sourceid), spool, stage)
            if result.success:
                spool.put_packages(result.builtpaths)
            results.append(result)
        logstore.done()
        self.deliver(id, results, logstore)
        return results

    def shell(self, id, logstore, latest=False, existing=False):
        if latest or existing:
            name = None
            if existing:
                name = id
            root = self.rootmanager.get_root_by_name(name,
                    self.packagemanager)
        else:
            root = self.rootmanager.create_new(id, self.packagemanager,
                    self.repos, logstore)
        root.mount()
        try:
            username, uid = self.build_user_info()
            if not existing and not latest:
                self.packagemanager.setup_repositories(root, self.repos,
                        logstore)
                root.add_user(username, uid)
                root.interactive_prepare(username, uid, self.packagemanager, self.repos,
                        logstore)
            root.interactive_shell(username)
        finally:
            root.umount()

    def set_interactive(self):
        self.interactive = True

build_types = Registry("builder type")
build_types.register("default", Builder)

def get_builder(rootmanager, packagemanager, buildconf, globalconf):
    klass_ = build_types.get_class(buildconf.build_type)
    instance = klass_(**klass_.load_config(rootmanager, packagemanager,
        buildconf, globalconf))
    return instance
