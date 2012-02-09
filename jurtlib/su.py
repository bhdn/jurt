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
import select
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

class AgentError(SuError):
    pass

class SudoNotSetup(SuError):
    pass

class SuWrapper:

    def add_user(self, username, uid, gid):
        raise NotImplementedError

    def copy(self, srcpath, dstpath, uid=None, gid=None, mode=None,
            cheap=False):
        raise NotImplementedError

    def copyout(self, srcpaths, dstpath, uid=None, gid=None, mode=None,
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
        cmdpolltime = float(suconf.command_poll_time)
        return dict(sucmd=sucmd, jurtrootcmd=jurtrootcmd,
                targetname=targetname,
                builduser=suconf.build_user,
                cmdpolltime=cmdpolltime)

    def __init__(self, sucmd, builduser, jurtrootcmd, targetname,
            cmdpolltime):
        self.sucmd = sucmd
        self.jurtrootcmd = jurtrootcmd
        self.targetname = targetname
        self.builduser = builduser
        self.cmdpolltime = cmdpolltime
        self.agentrunning = False
        self.agentproc = None
        self.agentcmdline = None
        self.agentcookie = str(id(self))

    def start(self):
        cmd = self.sucmd[:]
        cmd.extend(self.jurtrootcmd)
        cmd.append("--agent")
        cmd.extend(("--cookie", self.agentcookie))
        logger.debug("starting the superuser agent with %s", cmd)
        proc = subprocess.Popen(args=cmd, shell=False,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                stdin=subprocess.PIPE, bufsize=0)
        self.agentcmdline = cmd
        self.agentproc = proc
        self.agentrunning = True

    def _check_agent_output(self, data):
        returncode = None
        newdata = data
        magic = "\n" + self.agentcookie
        index = data.find(magic)
        if index != -1:
            newdata = data[:index]
            tail = data[index:]
            status = tail.split(None, 2)[1]
            if status == "OK":
                returncode = 0
            elif status == "ERROR":
                logger.debug("agent ERROR line: %s", tail)
                try:
                    rawreason = tail.split(None, 3)[2]
                except IndexError:
                    pass # ignore invalid stderr messages
                else:
                    try:
                        reason = int(rawreason)
                    except ValueError:
                        reason = 1
                    returncode = reason
        return returncode, newdata

    def _collect_from_agent(self, targetfile, outputlogger):
        rfd = self.agentproc.stdout.fileno()
        efd = self.agentproc.stderr.fileno()
        rl = [efd, rfd]
        returncode = None
        done = False
        while not done:
            try:
                nrl, _, nxl = select.select(rl, [], rl,
                        self.cmdpolltime)
            except KeyboardInterrupt:
                logger.debug("root agent possibly got SIGINT, we'd "
                        "better reap it to allow starting a new one\n")
                self.agentproc.wait()
                self.agentrunning = False
                raise
            if rfd in nrl:
                data = os.read(rfd, 8196)
                if not data:
                    #FIXME properly handle the exception
                    pass
                targetfile.write(data)
            if efd in nrl:
                data = os.read(efd, 8196)
                returncode, newdata = self._check_agent_output(data)
                targetfile.write(newdata)
                if returncode is not None:
                    done = True
            if self.agentproc.poll() is not None:
                self.agentrunning = False
                if outputlogger:
                    raise CommandError(self.agentproc.returncode,
                            self.agentcmdline, "(output available in log files)")
                else:
                    # If we are using the outputlogger, just let it
                    # fail with CommandError and make the stack trace
                    # available in the log files, otherwise, fail with
                    # the output from targetfile:
                    raise AgentError, ("Ouch! There was an unhandled "
                            "exception in the root helper "
                            "agent:\n%s\n" % (targetfile.getvalue()))
        return returncode

    def _exec_wrapper(self, type, args, root=None, arch=None,
            outputlogger=None, timeout=None, ignoreerrors=False,
            interactive=False, quiet=False, ignorestderr=False,
            remount=False):
        assert not (interactive and outputlogger)

        basecmd = self.jurtrootcmd[:]
        basecmd.extend(("--type", type))
        basecmd.extend(("--target", self.targetname))
        if timeout is not None:
            basecmd.extend(("--timeout", str(timeout)))
        if root is not None:
            basecmd.extend(("--root", root))
        if remount:
            basecmd.append("--remount")
        if arch is not None:
            basecmd.extend(("--arch", arch))
        if ignoreerrors:
            basecmd.append("--ignore-errors")
        if quiet:
            basecmd.append("--quiet")
        if ignorestderr:
            basecmd.append("--ignore-stderr")
        basecmd.extend(args)

        if interactive:
            fullcmd = self.sucmd[:]
            fullcmd.extend(basecmd)
            cmdline = subprocess.list2cmdline(fullcmd)
            proc = subprocess.Popen(args=fullcmd, shell=False, bufsize=-1)
            proc.wait()
            returncode = proc.returncode
            output = "(interactive command, no output)"
        else:
            cmdline = subprocess.list2cmdline(basecmd)
            if outputlogger and not quiet:
                outputlogger.write(">>>> running privilleged agent: %s\n" % (cmdline))
                outputlogger.flush()
            if not self.agentrunning:
                self.start()
            logger.debug("sending command to agent: %s", cmdline)
            self.agentproc.stdin.write(cmdline + "\n")
            self.agentproc.stdin.flush()
            if outputlogger:
                targetfile = outputlogger
            else:
                targetfile = StringIO()
            returncode = self._collect_from_agent(targetfile, outputlogger)
            if outputlogger:
                output = "(error in log available in log files)"
            else:
                output = targetfile.getvalue()
        # check for error:
        if returncode != 0:
            if timeout is not None and returncode == 124:
                # command timeout
                raise CommandTimeout, ("command timed out:\n%s\n" %
                        (cmdline))
            raise CommandError(returncode, cmdline, output)
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
            outputlogger=None, quiet=False, ignorestderr=False,
            remount=False):
        execargs = ["--run-as", user, "--"]
        execargs.extend(args)
        return self._exec_wrapper("runcmd", execargs, root=root, arch=arch,
                timeout=timeout, outputlogger=outputlogger, quiet=quiet,
                ignorestderr=ignorestderr, remount=False)

    def _perm_args(self, uid, gid, mode):
        args = []
        if uid is not None:
            args.extend(("-u", str(uid)))
        if gid is not None:
            args.extend(("-g", str(gid)))
        if mode is not None:
            args.extend(("-m", mode))
        return args

    def rename(self, srcpath, dstpath):
        args = [srcpath, dstpath]
        return self._exec_wrapper("rename", args)

    def mkdir(self, path_or_paths, uid=None, gid=None, mode="0755"):
        args = self._perm_args(uid, gid, mode)
        if isinstance(path_or_paths, basestring):
            args.append(path_or_paths)
        else:
            args.extend(path_or_paths)
        return self._exec_wrapper("mkdir", args)

    def create_devs(self, root):
        self._exec_wrapper("createdevs", root=root, args=[])

    def _copy_args(self, src_path_or_paths, dstpath, uid=None, gid=None, mode="0644"):
        args = self._perm_args(uid, gid, mode)
        if isinstance(src_path_or_paths, basestring):
            args.append(src_path_or_paths)
        else:
            args.extend(src_path_or_paths)
        args.append(dstpath)
        return args

    def copy(self, *args, **kwargs):
        return self._exec_wrapper("copy", self._copy_args(*args, **kwargs))

    def copyout(self, *args, **kwargs):
        return self._exec_wrapper("copyout", self._copy_args(*args, **kwargs))

    def cheapcopy(self, srcpath, dstpath):
        args = [srcpath, dstpath]
        return self._exec_wrapper("cheapcopy", args)

    def mount_virtual_filesystems(self, root, arch=None):
        return self._exec_wrapper("mountall", [], root=root, arch=arch)

    def umount_virtual_filesystems(self, root, arch=None):
        return self._exec_wrapper("umountall", [], root=root, arch=arch,
                ignoreerrors=False)

    def compress_root(self, root, file):
        args = [root, file]
        return self._exec_wrapper("rootcompress", args)

    def decompress_root(self, file, root):
        args = [root, file]
        return self._exec_wrapper("rootdecompress", args)

    def mount_tmpfs(self, root):
        return self._exec_wrapper("mounttmpfs", [root])

    def umount_tmpfs(self, root):
        return self._exec_wrapper("umounttmpfs", [root])

    def post_root_command(self, root=None, arch=None):
        return self._exec_wrapper("postcommand", [], root=root, arch=arch)

    def interactive_prepare_conf(self, username, root=None, arch=None):
        return self._exec_wrapper("interactiveprepare", [username],
                root=root, arch=arch)

    def interactive_shell(self, username, root=None, arch=None):
        return self._exec_wrapper("interactiveshell", [username],
                root=root, arch=arch, interactive=True, remount=True)

    def test_sudo(self, interactive=True):
        try:
            return self._exec_wrapper("test", [])
        except CommandError, e:
            raise SudoNotSetup

    def btrfs_snapshot(self, from_, to):
        logger.debug("creating btrfs snapshot from %s to %s" % (from_, to))
        return self._exec_wrapper("btrfssnapshot", [from_, to])

    def btrfs_create(self, dest):
        logger.debug("creating btrfs subvolume %s" % (dest))
        return self._exec_wrapper("btrfscreate", [dest])

    def destroy_root(self, path):
        return self._exec_wrapper("destroyroot", [path])

class SuChrootWrapper:

    def __init__(self, root, suwrapper):
        self.root = root
        self.suwrapper = suwrapper

    def add_user(self, username, uid, gid):
        return self.suwrapper.add_user(username, uid, gid, self.root.path)

    def run_package_manager(self, pmname, pmargs, outputlogger=None):
        return self.suwrapper.run_package_manager(pmname, pmargs,
                root=self.root.path, arch=self.root.arch, outputlogger=outputlogger)

    def run_as(self, args, user, timeout=None, outputlogger=None,
            quiet=False, ignorestderr=False, remount=False):
        return self.suwrapper.run_as(args, user=user, root=self.root.path,
                arch=self.root.arch, timeout=timeout,
                outputlogger=outputlogger, quiet=quiet,
                ignorestderr=ignorestderr,
                remount=False)

    def post_root_command(self):
        return self.suwrapper.post_root_command(root=self.root.path,
                arch=self.root.arch)

    def interactive_prepare_conf(self, username):
        return self.suwrapper.interactive_prepare_conf(username, root=self.root.path,
                arch=self.root.arch)

    def interactive_shell(self, username):
        return self.suwrapper.interactive_shell(username, root=self.root.path,
                arch=self.root.arch)

    def __getattr__(self, name):
        return getattr(self.suwrapper, name)

su_wrappers = Registry("sudo wrapper")
su_wrappers.register("jurt-root-wrapper", JurtRootWrapper)

def get_su_wrapper(targetname, suconf, globalconf):
    klass = su_wrappers.get_class(suconf.su_type)
    return klass(**klass.load_config(targetname, suconf, globalconf))
