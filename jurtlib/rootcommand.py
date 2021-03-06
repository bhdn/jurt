#!/usr/bin/python
#
# Copyright (c) 2012 Bogdano Arendartchuk <bogdano@mandriva.com.br>
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
import shlex
from jurtlib import Error, CommandError
from jurtlib.command import JurtCommand, CliError
from jurtlib.root import ChrootRootManager

PROC_MOUNTS = "/proc/mounts"

class RootCommand(JurtCommand):

    descr = "Runs a command privilleged user"
    usage = "%prog -t TYPE [options]"

    def init_parser(self, parser):
        super(RootCommand, self).init_parser(parser)
        parser.add_option("-t", "--type", default=None,
                help="Type of command to be run")
        parser.add_option("--pm", default=None,
                help="Package manager type used")
        parser.add_option("--target", default=None,
                help="Target name used (if applicable)")
        parser.add_option("--dry-run", default=False, action="store_true",
                help="Don't execute anything")
        parser.add_option("--root", type="string", default=None,
                help="execute inside chroot")
        parser.add_option("--remount", default=False, action="store_true",
                help=("appends the 'remount command' after any "
                    "chroot command line"))
        parser.add_option("--arch", type="string", default=None,
                help="set the arch used by --root")
        parser.add_option("--run-as", type="string", default=None,
                metavar="USER", help="Become USER (after chroot)")
        parser.add_option("-u", "--uid", type="string", default=None,
                help="set UID used")
        parser.add_option("-g", "--gid", type="string", default=None,
                help="set GID used")
        parser.add_option("-m", "--mode", type="string", default=None,
                help="Destination file mode")
        parser.add_option("--timeout", type="int", default=None,
                help="Command execution timeout")
        parser.add_option("--ignore-errors", default=False,
                action="store_true",
                help="Command execution timeout")
        parser.add_option("--agent", default=False, action="store_true",
                help="Runs in agent mode")
        parser.add_option("--cookie", type="string", default=None,
                help=("Set the cookie to use as prefix in control "
                    "output"))
        parser.add_option("--ignore-stderr", default=False,
                action="store_true",
                help=("Redirect stderr to /dev/null"))

    def config_files(self, config):
        return [config.conf.system_file]

    def run(self):
        if self.opts.agent:
            self._run_as_agent()
        else:
            self._handle_command()

    def _run_as_agent(self):
        import shlex
        import select

        if self.opts.cookie is None:
            raise CliError, ("the option --cookie is required when "
                    "running in agent mode")
        cookiepart = "%s " % (self.opts.cookie)
        sys.stderr.write("waiting for commands\n")
        while True:
            rl, wl, xl = select.select([sys.stdin.fileno()], [],
                    [sys.stdin.fileno()])
            if rl:
                line = sys.stdin.readline()
                if not line:
                    # we'd better be dead as nothing will arrive for us
                    return
                else:
                    cmdargs = shlex.split(line)[1:]
                    parser = self.create_parser()
                    self.init_parser(parser)
                    self.opts, self.args[:] = self.parse_args(parser, cmdargs)
                    try:
                        try:
                            self._handle_command()
                        except CommandError, e:
                            sys.stderr.write("\n%sERROR %d %s\n" %
                                    (cookiepart, e.returncode, e))
                        except Error, e:
                            sys.stderr.write("\n%sERROR %s\n" %
                                    (cookiepart, e))
                        else:
                            sys.stderr.write("\n%sOK\n" % (cookiepart))
                        sys.stderr.flush()
                    except IOError, e:
                        if e.errno == 32: # broken pipe
                            return
                        raise

    def _handle_command(self):
        if not self.opts.type:
            raise CliError, "--type is mandatory"
        mname = "cmd_" + self.opts.type
        try:
            getattr(self, mname)()
        except AttributeError:
            etype, exc, tb = sys.exc_info()
            if tb.tb_next is None:
                raise CliError, "invalid operation type: %s" % self.opts.type
            raise

    def _requires_target(f):
        def w(self):
            if self.opts.target is None:
                raise CliError, "--target is mandatory for this --type"
            try:
                target = self.jurt.init_target(self.opts.target)
            except KeyError:
                raise CliError, "invalid target: %s" % (self.opts.target)
            self.target = target
            return f(self)
        return w

    def _requires_root(f):
        def w(self):
            if not self.opts.root:
                raise CliError, "--root is required for this command"
            return f(self)
        return w

    def _requires_chroot(f):
        def w(self):
            if not isinstance(self.target.rootmanager, ChrootRootManager):
                raise CliError, "root for the target %s is not a chroot"
            return f(self)
        return w

    def _exec(self, args, exit=True, error=True, interactive=False,
            allowchroot=True):
        import subprocess
        allcmd = []
        if self.opts.timeout is not None:
            allcmd.extend(("timeout", str(self.opts.timeout)))
        if self.opts.root and allowchroot:
            if self.opts.arch:
                sysarch = self.target.packagemanager.system_arch()
                if self.opts.arch != sysarch:
                    allcmd.extend(self.target.rootmanager.setarch_command(sysarch,
                        self.opts.arch))
            self.target.rootmanager.check_valid_subdir(self.opts.root)
            chrootcmd = self.target.rootmanager.chroot_command()
            allcmd.extend(chrootcmd)
            allcmd.append(self.opts.root)
        if self.opts.remount:
            allcmd.extend(self.target.rootmanager.remount_wrapper_command())
        if self.opts.run_as:
            sucmd = self.target.rootmanager.su_command()
            allcmd.extend(sucmd)
            allcmd.append(self.opts.run_as)
            allcmd.append("-c")
            allcmd.append(subprocess.list2cmdline(args)) # blarg
        else:
            allcmd.extend(args)
        if self.opts.ignore_stderr:
            stderr = open(os.devnull)
        else:
            stderr = None
        cmdline = subprocess.list2cmdline(allcmd)
        if not interactive and not self.opts.quiet:
            sys.stderr.write(">>>>>> running: %s\n" % (cmdline))
            sys.stderr.flush()
        if not self.opts.dry_run:
            p = subprocess.Popen(args=allcmd, stderr=stderr, shell=False)
            p.wait()
            if not self.opts.ignore_errors:
                if p.returncode != 0:
                    msg = ("command failed with %d (output above "
                            "^^^^^^^^^^)\n" % p.returncode)
                    # in case of timeout (err 124), only return the error
                    # code to the caller
                    if exit and not (self.opts.timeout
                                     and p.returncode == 124):
                        raise CliError, msg
                    else:
                        if error:
                            sys.stderr.write(msg + "\n")
                        raise CommandError(p.returncode,
                                subprocess.list2cmdline(allcmd), "")

    @_requires_target
    def cmd_runpm(self):
        if self.opts.pm is None:
            raise CliError, "the option --pm is mandatory"
        self.target.packagemanager.validate_cmd_args(self.opts.pm, self.args)
        self._exec(self.target.packagemanager.cmd_args(self.opts.pm, self.args))

    def _install_cmd(self, dir=False):
        cmd = [self.config.root.install_command]
        if dir:
            cmd.append("-d")
        if self.opts.uid:
            cmd.extend(("-o", self.opts.uid))
        if self.opts.gid:
            cmd.extend(("-g", self.opts.gid))
        if self.opts.mode:
            cmd.extend(("-m", self.opts.mode))
        return cmd

    @_requires_target
    def cmd_adduser(self):
        if not self.args:
            raise CliError, "you must provide an username"
        cmd = shlex.split(self.config.root.adduser_command)
        cmd.extend(("-u", self.opts.uid))
        cmd.append(self.args[0])
        if not self.opts.dry_run:
            self._exec(cmd)

    @_requires_target
    def cmd_copy(self):
        if len(self.args) < 2:
            raise CliError, "copy requires two operands"
        source = self.args[0]
        dest = self.args[1]
        self.target.rootmanager.check_valid_subdir(dest)
        cmd = self._install_cmd()
        cmd.append(source)
        cmd.append(dest)
        if not self.opts.dry_run:
            self._exec(cmd)

    @_requires_target
    def cmd_copyout(self):
        if len(self.args) < 2:
            raise CliError, "copy requires two operands"
        sources = self.args[:-1]
        dest = self.args[-1]
        for source in sources:
            self.target.rootmanager.check_valid_subdir(source)
        self.target.rootmanager.check_valid_outdir(dest)
        cmd = self._install_cmd()
        cmd.extend(sources)
        cmd.append(dest)
        if not self.opts.dry_run:
            self._exec(cmd)


    @_requires_target
    def cmd_cheapcopy(self):
        from jurtlib import util
        if len(self.args) < 2:
            raise CliError, "copy requires two operands"
        source = self.args[0]
        dest = self.args[1]
        self.target.rootmanager.check_valid_subdir(dest)
        copyopts = "-af"
        if util.same_partition(source, dest):
            copyopts += "l"
        cmd = ["cp", copyopts, source, dest]
        if not self.opts.dry_run:
            self._exec(cmd)

    @_requires_target
    def cmd_mkdir(self):
        for arg in self.args:
            self.target.rootmanager.check_valid_subdir(arg)
            cmd = self._install_cmd(dir=True)
            cmd.append(arg)
            if not self.opts.dry_run:
                self._exec(cmd)

    def _check_build_user(self, username):
        # checks whether the user being used inside the chroot is the one
        # set in configuration, if not, then it must be some user that is
        # member of the jurt group
        import grp
        sysbuilder = self.target.builder.build_user_info()[0]
        if username != sysbuilder:
            groupname = self.config.root.jurt_group
            try:
                group = grp.getgrnam(groupname)
            except KeyError:
                raise CliError, ("the group %s does not exist, cannot check "
                        "--run-as" % (groupname))
            if username not in group.gr_mem:
                raise CliError, ("the user %s is not a member of the group "
                        "%s" % (username, groupname))

    @_requires_target
    @_requires_root
    def cmd_runcmd(self):
        if not self.opts.run_as:
            raise CliError, "--run-as is required for run"
        self._check_build_user(self.opts.run_as)
        if not self.opts.dry_run:
            self._exec(self.args)

    def _mount_info(self):
        if not self.args:
            raise CliError, "you must provide a mount type"
        typename = self.args[0]
        try:
            mountinfo = MOUNT_TYPES[typename]
        except KeyError:
            raise CliError, "invalid mount type: %s" % (typename)
        return mountinfo

    def _parse_proc_mounts(self):
        if not os.path.exists(PROC_MOUNTS):
            raise Error, "%s is needed when mounting" % (PROC_MOUNTS)
        mounted = set()
        with open(PROC_MOUNTS) as f:
            for line in f:
                line = line.strip()
                if not line.startswith("#"):
                    fields = line.split()
                    if len(fields) > 1:
                        # /proc/mounts represents spaces as \040; too lazy
                        # for proper parsing:
                        path = fields[1].replace("\\040", " ")
                        mounted.add(os.path.abspath(path) + "/")
        return frozenset(mounted)

    @_requires_target
    @_requires_root
    @_requires_chroot
    def cmd_mountall(self):
        mounted = self._parse_proc_mounts()
        for devpath, mountpoint, fsname, options in self.target.rootmanager.mount_points():
            absmntpoint = os.path.abspath(self.opts.root + "/" +
                    mountpoint) + "/"
            if not os.path.exists(absmntpoint):
                try:
                    os.mkdir(absmntpoint)
                except (IOError, OSError), e:
                    raise Error, "failed to create mountpoint: %s" % e
            if absmntpoint not in mounted:
                if fsname == "bind":
                    args = ["mount", "--rbind", devpath, absmntpoint]
                    chroot = False
                else:
                    args = ["mount", "-o", options, "-t", fsname, devpath, mountpoint]
                    chroot = True
                if not self.opts.dry_run:
                    self._exec(args, allowchroot=chroot)

    @_requires_target
    @_requires_root
    @_requires_chroot
    def cmd_umountall(self):
        mounted = self._parse_proc_mounts()
        for devpath, mountpoint, fsname, options in self.target.rootmanager.mount_points():
            absmntpoint = os.path.abspath(self.opts.root + "/" +
                    mountpoint) + "/"
            if absmntpoint in mounted:
                args = ["umount", mountpoint]
                if not self.opts.dry_run:
                    self._exec(args)

    @_requires_target
    @_requires_root
    @_requires_chroot
    def cmd_createdevs(self):
        prevumask = os.umask(0)
        try:
            for devname, type, major, minor, mode in self.target.rootmanager.devices():
                abspath = os.path.abspath(self.opts.root + os.path.sep + devname)
                absdir = os.path.dirname(abspath)
                if not os.path.exists(absdir):
                    try:
                        os.makedirs(absdir)
                    except EnvironmentError, e:
                        raise Error, ("failed to create device directory: %s" %
                                (e))
                try:
                    dev = os.makedev(major, minor)
                    os.mknod(abspath, type | mode, dev)
                except EnvironmentError, e:
                    raise Error, "failed to create device: %s" % (e)
        finally:
            os.umask(prevumask)

    def _tmp_cachepath(self, cachepath):
        import tempfile
        base = os.path.dirname(cachepath)
        prefix = os.path.basename(cachepath) + "."
        return tempfile.mktemp(dir=base, prefix=prefix)

    def _comp_decomp(self, comp=False):
        if not self.args:
            raise CliError, "a root path is mandatory"
        root = self.args[0]
        file = self.args[1]
        self.target.rootmanager.check_valid_subdir(root)
        try:
            if comp:
                fun = self.target.rootmanager.root_compress_command
            else:
                fun = self.target.rootmanager.root_decompress_command
        except AttributeError:
            raise CliError, "this target doesn't support using compressed root"
        if comp:
            tmpname = self._tmp_cachepath(file)
        else:
            tmpname = file
        args = fun(root, tmpname)
        if not self.opts.dry_run:
            self._exec(args, exit=False)
            if comp:
                os.rename(tmpname, file)

    @_requires_target
    def cmd_rootcompress(self):
        self._comp_decomp(True)

    @_requires_target
    def cmd_rootdecompress(self):
        self._comp_decomp(False)

    @_requires_target
    @_requires_root
    def cmd_postcommand(self):
        args = self.target.rootmanager.su_for_post_command()
        args.append(self.target.rootmanager.post_command())
        if not self.opts.dry_run:
            self._exec(args)

    @_requires_target
    @_requires_root
    def cmd_interactiveshell(self):
        from jurtlib.template import template_expand
        if not self.args:
            raise CliError, "username is mandatory in args"
        if not self.target.rootmanager.allows_interactive_shell():
            raise CliError, "interactive configuration not allowed "\
                    "for this target"
        args = self.target.rootmanager.sudo_interactive_shell_command()
        args.extend(("-u", self.args[0]))
        rawcmd = self.target.rootmanager.interactive_shell_command()
        env = {"target": self.target.name, "root": self.opts.root}
        cmdline = template_expand(rawcmd, env)
        args.extend(shlex.split(cmdline))
        if not self.opts.dry_run:
            try:
                self._exec(args, error=False, exit=False, interactive=True)
            except CommandError, e:
                if e.returncode == 127:
                    raise
                # else: it may simply be and 'exit' from the shell

    @_requires_target
    @_requires_root
    def cmd_interactiveprepare(self):
        from jurtlib.template import template_expand
        if not self.args:
            raise CliError, "username is mandatory in args"
        user = self.args[0]
        allowedcmds = self.target.packagemanager.allowed_pm_commands()
        cmdsline = ",".join(allowedcmds)
        rawline = self.config.root.sudo_pm_allow_format
        env = {"user": user, "commands": cmdsline}
        sudoline = template_expand(rawline, env)
        sudoerspath = os.path.abspath(self.opts.root+ "/" +
                self.config.root.sudoers)
        f = open(sudoerspath, "a")
        f.write(sudoline + "\n")
        f.close()

    def cmd_test(self):
        if os.geteuid() != 0:
            raise Error, "i am not root"

    @_requires_target
    def cmd_btrfssnapshot(self):
        if len(self.args) != 2:
            raise CliError, "unexpected number of args"
        from_ = self.args[0]
        to = self.args[1]
        self.target.rootmanager.check_valid_subdir(from_)
        self.target.rootmanager.check_valid_subdir(to)
        args = self.target.rootmanager.snapsvcmd[:]
        args.append(from_)
        args.append(to)
        self._exec(args)

    @_requires_target
    def cmd_btrfscreate(self):
        if len(self.args) != 1:
            raise CliError, "unexpected number of args"
        dest = self.args[0]
        self.target.rootmanager.check_valid_subdir(dest)
        args = self.target.rootmanager.newsvcmd[:]
        args.append(dest)
        self._exec(args)

    @_requires_target
    def cmd_rename(self):
        if len(self.args) != 2:
            raise CliError, "unexpected number of args"
        src, dst = self.args
        self.target.rootmanager.check_valid_subdir(src)
        self.target.rootmanager.check_valid_subdir(dst)
        os.rename(src, dst) # TODO what else to check? permissions?

    @_requires_target
    def cmd_destroyroot(self):
        if len(self.args) != 1:
            raise CliError, "unexpected number of args"
        self.target.rootmanager.check_valid_subdir(self.args[0])
        # WARN: destroycmd is a specific of Chroot:
        args = self.target.rootmanager.root_destroy_command()
        args.append(self.args[0])
        self._exec(args)

    @_requires_target
    def cmd_mounttmpfs(self):
        if len(self.args) != 1:
            raise CliError, "unexpected number of args"
        self.target.rootmanager.check_valid_subdir(self.args[0])
        args = self.target.rootmanager.mount_root_command(self.args[0])
        self._exec(args)

    @_requires_target
    def cmd_umounttmpfs(self):
        if len(self.args) != 1:
            raise CliError, "unexpected number of args"
        self.target.rootmanager.check_valid_subdir(self.args[0])
        args = self.target.rootmanager.umount_root_command(self.args[0])
        self._exec(args)

