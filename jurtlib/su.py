import os
import subprocess
import logging
from jurtlib import Error, CommandError
from jurtlib.registry import Registry
from cStringIO import StringIO

logger = logging.getLogger("jurt.su")

def my_username():
    import pwd
    uid = os.geteuid()
    try:
        pw = pwd.getpwuid(uid)
        name = pw.pw_name
    except KeyError:
        name = str(uid)
    return name, uid

class CommandTimeout(Error):
    pass

class SuError(Error):
    pass

class SudoNotSetup(SuError):
    pass

class SuWrapper:

    def add_user(self, username, uid, gid):
        raise NotImplementedError

    def copy(self, srcpath, dstpath, uid=None, gid=None, mode=None,
            cheap=False):
        raise NotImplementedError

    def copyout(self, srcpath, dstpath, uid=None, gid=None, mode=None,
            cheap=False):
        raise NotImplementedError

    def run_package_manager(self, pmname, args):
        raise NotImplementedError

class JurtRootWrapper(SuWrapper):

    @classmethod
    def load_config(class_, targetname, suconf, globalconf):
        import shlex
        sucmd = shlex.split(suconf.sudo_command)
        jurtrootcmd = shlex.split(suconf.jurt_root_command_command)
        return dict(sucmd=sucmd, jurtrootcmd=jurtrootcmd,
                targetname=targetname,
                builduser=suconf.build_user)

    def __init__(self, sucmd, builduser, jurtrootcmd, targetname):
        self.sucmd = sucmd
        self.jurtrootcmd = jurtrootcmd
        self.targetname = targetname
        self.builduser = builduser

    def _exec_wrapper(self, type, args, root=None, arch=None,
            outputlogger=None, timeout=None, ignoreerrors=False,
            interactive=False):
        cmd = self.sucmd[:]
        cmd.extend(self.jurtrootcmd)
        cmd.extend(("--type", type))
        cmd.extend(("--target", self.targetname))
        if timeout is not None:
            cmd.extend(("--timeout", str(timeout)))
        if root is not None:
            cmd.extend(("--root", root))
        if arch is not None:
            cmd.extend(("--arch", arch))
        if ignoreerrors:
            cmd.append("--ignore-errors")
        cmd.extend(args)
        cmdline = subprocess.list2cmdline(cmd)
        stderr = subprocess.STDOUT
        stdin = None
        if outputlogger:
            stdout = outputlogger
            stdout.write(">>>> running privilleged helper: %s\n" % (cmdline))
            stdout.flush()
        elif interactive:
            stdout = stderr = None
        else:
            stdout = subprocess.PIPE
            if os.path.exists("/dev/null"):
                stdin = open("/dev/null") # FIXME test
        proc = subprocess.Popen(args=cmd, shell=False, stdout=stdout,
                stderr=stderr)
        proc.wait()
        if stdout is subprocess.PIPE:
            output = proc.stdout.read()
        else:
            output = "(no output)"
        if proc.returncode != 0:
            if timeout is not None and proc.returncode == 124:
                # command timeout
                raise CommandTimeout, ("command timed out:\n%s\n" %
                        (cmdline))
            raise CommandError(proc.returncode, cmdline, output)
        return output

    def add_user(self, username, uid, root=None, arch=None):
        return self._exec_wrapper("adduser", ["-u", str(uid), username],
                root=root, arch=arch)

    def run_package_manager(self, pmname, pmargs, root=None, arch=None,
            outputlogger=None):
        execargs = ["--pm", pmname, "--"]
        execargs.extend(pmargs)
        return self._exec_wrapper("runpm", execargs, root=root, arch=arch,
                outputlogger=outputlogger)

    def run_as(self, args, user, root=None, arch=None, timeout=None,
            outputlogger=None):
        execargs = ["--run-as", user, "--"]
        execargs.extend(args)
        return self._exec_wrapper("run", execargs, root=root, arch=arch,
                timeout=timeout, outputlogger=outputlogger)

    def mkdir(self, path):
        return self._exec_wrapper("mkdir", [path])

    def _copy_args(self, srcpath, dstpath, uid=None, gid=None, mode="0644"):
        args = []
        if uid is not None:
            args.extend(("-u", str(uid)))
        if gid is not None:
            args.extend(("-g", str(gid)))
        if mode is not None:
            args.extend(("-m", mode))
        args.append(srcpath)
        args.append(dstpath)
        return args

    def copy(self, *args, **kwargs):
        return self._exec_wrapper("copy", self._copy_args(*args, **kwargs))

    def copyout(self, *args, **kwargs):
        return self._exec_wrapper("copyout", self._copy_args(*args, **kwargs))

    def cheapcopy(self, srcpath, dstpath):
        args = [srcpath, dstpath]
        return self._exec_wrapper("cheapcopy", args)

    def mount(self, alias, root, arch=None):
        args = [alias]
        return self._exec_wrapper("mount", args, root=root, arch=arch)

    def umount(self, alias, root, arch=None):
        args = [alias]
        return self._exec_wrapper("umount", args, root=root, arch=arch,
                ignoreerrors=False)

    def compress_root(self, root, file):
        args = [root, file]
        return self._exec_wrapper("rootcompress", args)

    def decompress_root(self, file, root):
        args = [root, file]
        return self._exec_wrapper("rootdecompress", args)

    def post_root_command(self, root=None, arch=None):
        return self._exec_wrapper("postcommand", [], root=root, arch=arch)

    def interactive_prepare_conf(self, username, root=None, arch=None):
        return self._exec_wrapper("interactiveprepare", [username],
                root=root, arch=arch)

    def interactive_shell(self, username, root=None, arch=None):
        return self._exec_wrapper("interactiveshell", [username],
                root=root, arch=arch, interactive=True)

    def test_sudo(self, interactive=True):
        try:
            return self._exec_wrapper("test", [], interactive=True)
        except CommandError, e:
            raise SudoNotSetup

    def btrfs_snapshot(self, from_, to):
        logger.debug("creating btrfs snapshot from %s to %s" % (from_, to))
        return self._exec_wrapper("btrfssnapshot", [from_, to])

    def btrfs_create(self, dest):
        logger.debug("creating btrfs subvolume %s" % (dest))
        return self._exec_wrapper("btrfscreate", [dest])

class SuChrootWrapper:

    def __init__(self, path, arch, suwrapper):
        self.path = path
        self.arch = arch
        self.suwrapper = suwrapper

    def add_user(self, username, uid, gid):
        return self.suwrapper.add_user(username, uid, gid, self.path)

    def run_package_manager(self, pmname, pmargs, outputlogger=None):
        return self.suwrapper.run_package_manager(pmname, pmargs,
                root=self.path, arch=self.arch, outputlogger=outputlogger)

    def run_as(self, args, user, timeout=None, outputlogger=None):
        return self.suwrapper.run_as(args, user=user, root=self.path,
                arch=self.arch, timeout=timeout, outputlogger=outputlogger)

    def post_root_command(self):
        return self.suwrapper.post_root_command(root=self.path, arch=self.arch)

    def interactive_prepare_conf(self, username):
        return self.suwrapper.interactive_prepare_conf(username, root=self.path,
                arch=self.arch)

    def interactive_shell(self, username):
        return self.suwrapper.interactive_shell(username, root=self.path,
                arch=self.arch)

    def __getattr__(self, name):
        return getattr(self.suwrapper, name)

su_wrappers = Registry("sudo wrapper")
su_wrappers.register("jurt-root-wrapper", JurtRootWrapper)

def get_su_wrapper(targetname, suconf, globalconf):
    klass = su_wrappers.get_class(suconf.su_type)
    return klass(**klass.load_config(targetname, suconf, globalconf))
