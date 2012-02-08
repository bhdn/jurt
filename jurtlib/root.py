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
import abc
import os
import shlex
import subprocess
import logging
import time
from jurtlib import Error, util
from jurtlib.registry import Registry
from jurtlib.su import SuChrootWrapper, my_username
from jurtlib.configutil import parse_bool, parse_conf_fields

logger = logging.getLogger("jurt.root")

class RootError(Error):
    pass

class ChrootError(RootError):
    pass

class Active:
    pass
class Temp:
    pass
class Keep:
    pass
class Old:
    pass
class Tmpfs:
    pass

class DontCare:
    """Whether it must be interactive or not"""

STATE_NAMES = {Temp: "temp", Active: "active", Keep: "keep",
    Old: "old", Tmpfs: "tmpfs"}
STATE_DIRS = dict((v, k) for k, v in STATE_NAMES.iteritems())

class Root(object):
    """
    A root object must be in one of these states:

    - temp: roots being created, cannot be removed
    - active: packages can be built, files copied into, mount points,
      cannot be removed
    - keep: roots that were pinned and can be reused soon
    - old: can be removed at any time, can go to active state at any time
    """
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def copy_in(self, files, dstpath):
        raise NotImplementedError

    @abc.abstractmethod
    def copy_out(self, sourcepaths, dstpath):
        raise NotImplementedError

    @abc.abstractmethod
    def mkdir(self, path_or_paths, uid=None, gid=None, mode=None):
        raise NotImplementedError

    @abc.abstractmethod
    def add_user(self, username, uid):
        raise NotImplementedError

    @abc.abstractmethod
    def make_spool_reachable(self, spool):
        raise NotImplementedError

    @abc.abstractmethod
    def glob(self, globexpr):
        raise NotImplementedError

    @abc.abstractmethod
    def external_path(self, localpath):
        """Should provide an pointer from the outside world to know how to
        find files inside the root, mostly for error messages"""
        raise NotImplementedError

    @abc.abstractmethod
    def activate(self):
        raise NotImplementedError

    @abc.abstractmethod
    def deactivate(self):
        raise NotImplementedError

    @abc.abstractmethod
    def destroy(self):
        raise NotImplementedError

    @abc.abstractmethod
    def interactive_prepare(self, username, uid, packagemanager, repos,
            logstore):
        raise NotImplementedError

class RootManager(object):

    __metaclass__ = abc.ABCMeta

    @classmethod
    @abc.abstractmethod
    def load_config(class_, suwrapper, rootconf, globalconf):
        raise NotImplementedError

    @abc.abstractmethod
    def create_new(self, name, packagemanager, repos, logger, interactive):
        raise NotImplementedError

    @abc.abstractmethod
    def su(self):
        """Returns an object that allows runnning privilleged commands from
        inside the root"""
        raise NotImplementedError

    @abc.abstractmethod
    def check_valid_subdir(self, path):
        """Checks whether the path is inside the roots directory"""
        raise NotImplementedError

    @abc.abstractmethod
    def destroy(self, root):
        raise NotImplementedError

    @abc.abstractmethod
    def test_sudo(self):
        raise NotImplementedError

    @abc.abstractmethod
    def get_root_by_name(self, name, packagemanager, interactive=False):
        raise NotImplementedError

    @abc.abstractmethod
    def activate_root(self, root):
        raise NotImplementedError

    @abc.abstractmethod
    def list_roots(self):
        raise NotImplementedError

    @abc.abstractmethod
    def clean(self):
        raise NotImplementedError

    def invalidate(self, interactive=DontCare):
        raise RootError, "this root type does not support caching"

    @abc.abstractmethod
    def allows_interactive_shell(self):
        raise NotImplementedError

class ChrootSpool:

    def __init__(self, path, repopath):
        self.path = path
        self.repopath = repopath

    def in_root_path(self):
        return self.repopath

    def destroy(self):
        # hardlinks, let them die with the chroot
        pass

class Chroot(Root):
    
    def __init__(self, manager, path, arch, state=Temp, interactive=False):
        self.manager = manager
        self.path = path
        self.arch = arch
        self.state = state
        self.interactive = interactive
        self.chrootsu = SuChrootWrapper(self, self.manager.su())

    def add_user(self, username, uid):
        self.manager.su().add_user(username, uid, root=self.path,
                arch=self.arch)

    def copy_in(self, localsrcpath, rootdestpath, uid=None, gid=None,
            mode="0644", cheap=False, sameuser=False):
        realdestpath = os.path.abspath(self.path + "/" + rootdestpath)
        destpath = os.path.join(rootdestpath,
                os.path.basename(localsrcpath))
        if sameuser:
            from jurtlib.cmd import run
            args = self.manager.putcopycmd[:]
            args.append(localsrcpath)
            args.append(realdestpath)
            run(args)
        else:
            self.manager.su().copy(localsrcpath, realdestpath, uid=uid,
                    gid=gid, mode=mode)
        return destpath

    def copy_out(self, sourcepaths, dstpath, uid=None, gid=None,
            mode="0644", sameuser=False):
        realsources = [os.path.abspath(self.path + "/" + path)
            for path in sourcepaths]
        if sameuser:
            from jurtlib.cmd import run
            args = self.manager.putcopycmd[:]
            args.extend(realsources)
            args.append(dstpath)
            run(args)
        else:
            self.manager.su().copyout(realsources, dstpath, uid=uid, gid=gid,
                    mode=mode)

    def mkdir(self, path_or_paths, uid=None, gid=None, mode="0755"):
        if isinstance(path_or_paths, basestring):
            paths = [path_or_paths]
        else:
            paths = path_or_paths
        realpaths = [os.path.abspath(self.path + "/" + path) for path in paths]
        self.manager.su().mkdir(realpaths, uid=uid, gid=gid, mode=mode)

    def su(self):
        #TODO kill su()
        return self.chrootsu

    def make_spool_reachable(self, spool):
        dest = os.path.abspath(self.path + "/" + self.manager.spooldir)
        self.manager.su().cheapcopy(spool.path, dest)
        return ChrootSpool(dest, self.manager.spooldir)

    def _strip_path(self, path): 
        basepath = os.path.abspath(self.path)
        abspath = os.path.abspath(path)
        subpath = "/" + abspath[len(basepath):]
        return os.path.abspath(subpath)

    def glob(self, globexpr):
        import glob
        expr = os.path.abspath(self.path + "/" + globexpr)
        found = [self._strip_path(p) for p in glob.glob(expr)]
        return found

    def external_path(self, localpath):
        return os.path.abspath(self.path + "/" + localpath)

    def interactive_prepare(self, username, uid, packagemanager, repos, logstore):
        self.su().interactive_prepare_conf(username)

    def interactive_shell(self, username):
        if not self.manager.allows_interactive_shell():
            raise RootError, "interactive shell not allowed in target"\
                    " configuration"
        logger.info("you are inside %s" % (self.path))
        self.su().interactive_shell(username)

    def activate(self):
        self.manager.activate_root(self)
        self.manager.su().mount_virtual_filesystems(self.path, self.arch)

    def deactivate(self):
        self.manager.su().umount_virtual_filesystems(self.path, self.arch)
        self.manager.deactivate_root(self)

    def destroy(self, interactive=False):
        self.manager.destroy(self, interactive)

class ChrootRootManager(RootManager):

    @classmethod
    def _parse_arch_map(class_, rawmap):
        rawmap = rawmap.strip()
        map = {}
        if rawmap:
            for rawentry in rawmap.split(";"):
                try:
                    name, cmd = rawentry.split(None, 1)
                except ValueError:
                    logger.warn("invalid format in arch-map configuration "
                            "option, ignoring it")
                else:
                    map[name] = shlex.split(cmd)
        return map

    @classmethod
    def _parse_mount_points(class_, rawvalue):
        return parse_conf_fields(rawvalue, 4, "mountpoint")

    @classmethod
    def _parse_binds(class_, rawvalue):
        return parse_conf_fields(rawvalue, 2, "binds")

    @classmethod
    def _parse_devs(class_, rawvalue):
        import stat
        typemap = {"b": stat.S_IFBLK, "c": stat.S_IFCHR}
        rawdevs = parse_conf_fields(rawvalue, 5, "devices")
        devs = []
        try:
            devs = [(name, typemap[type], int(rawmajor), int(rawminor),
                     int(rawmode, 8))
                    for (name, type, rawmajor, rawminor, rawmode) in rawdevs]
        except KeyError:
            logger.warn("invalid type for device in list of devices: %s",
                    rawvalue)
        except ValueError:
            logger.warn("invalid integer in list of devices: %s", rawvalue)
        return devs

    @classmethod
    def _parse_max_root_age(class_, rawvalue):
        try:
            days = int(rawvalue)
        except ValueError, e:
            logger.warn("invalid value for max-root-age: %r" % (rawvalue))
        seconds = days * 24 * 60 * 60
        return seconds

    @classmethod
    def load_config(class_, suwrapper, rootconf, globalconf):
        copyfiles = shlex.split(rootconf.root_copy_files)
        postcmd = rootconf.root_post_command.strip()
        arch = rootconf.arch
        archmap = class_._parse_arch_map(rootconf.arch_map)
        allowshell = parse_bool(rootconf.allow_interactive_shell)
        keepstatedir = rootconf.keep_roots_dir
        oldstatedir = rootconf.old_roots_dir
        tempstatedir = rootconf.temp_roots_dir
        activestatedir = rootconf.active_roots_dir
        latestsuffix_build = rootconf.latest_build_suffix
        latestsuffix_interactive = rootconf.latest_interactive_suffix
        putcopycmd = shlex.split(rootconf.put_copy_command)
        destroycmd = shlex.split(rootconf.chroot_destroy_command)
        targetfile = rootconf.chroot_target_file.strip()
        interactivefile = rootconf.chroot_interactive_file.strip()
        keepfile = rootconf.chroot_keep_file.strip()
        mountpoints = class_._parse_mount_points(rootconf.chroot_mountpoints)
        binds = class_._parse_binds(rootconf.chroot_binds)
        devs = class_._parse_devs(rootconf.chroot_devs)
        maxrootage = class_._parse_max_root_age(rootconf.root_max_age)
        return dict(topdir=rootconf.roots_path, suwrapper=suwrapper,
            spooldir=rootconf.chroot_spool_dir,
            donedir=rootconf.success_dir,
            faildir=rootconf.failure_dir,
            copyfiles=copyfiles,
            postcmd=postcmd,
            arch=arch,
            archmap=archmap,
            allowshell=allowshell,
            activestatedir=activestatedir,
            tempstatedir=tempstatedir,
            oldstatedir=oldstatedir,
            keepstatedir=keepstatedir,
            latestsuffix_build=latestsuffix_build,
            latestsuffix_interactive=latestsuffix_interactive,
            putcopycmd=putcopycmd,
            destroycmd=destroycmd,
            targetfile=targetfile,
            interactivefile=interactivefile,
            keepfile=keepfile,
            mountpoints=mountpoints,
            binds=binds,
            devs=devs,
            maxrootage=maxrootage)

    def __init__(self, topdir, arch, archmap, spooldir, donedir, faildir, suwrapper,
            copyfiles, postcmd, allowshell, activestatedir, tempstatedir,
            oldstatedir, keepstatedir, latestsuffix_build,
            latestsuffix_interactive, putcopycmd, destroycmd, targetfile,
            interactivefile, keepfile, mountpoints, binds, devs, maxrootage):
        self.topdir = topdir
        self.suwrapper = suwrapper
        self.spooldir = spooldir
        self.donedir = donedir
        self.faildir = faildir
        self.copyfiles = copyfiles
        self.postcmd = postcmd
        self.arch = arch
        self.archmap = archmap
        self.allowshell = allowshell
        self.activestatedir = activestatedir
        self.keepstatedir = keepstatedir
        self.oldstatedir = oldstatedir
        self.tempstatedir = tempstatedir
        self.latestsuffix_build = latestsuffix_build
        self.latestsuffix_interactive = latestsuffix_interactive
        self.putcopycmd = putcopycmd
        self.destroycmd = destroycmd
        self.targetfile = targetfile
        self.interactivefile = interactivefile
        self.keepfile = keepfile
        self.mountpoints = mountpoints
        self.binds = binds
        self.devs = devs
        self.maxrootage = maxrootage

    def su(self):
        return self.suwrapper

    def _copy_files_from_conf(self, root):
        for path in self.copyfiles:
            root.copy_in(path, os.path.dirname(path))

    def _create_metadata_files(self, root, interactive):
        from tempfile import NamedTemporaryFile
        files = [(self.targetfile, self.targetname)]
        if interactive:
            files.append((self.interactivefile, "yes"))
        for path, value in files:
            tf = NamedTemporaryFile()
            tf.write(value + "\n")
            tf.flush()
            root.copy_in(tf.name, path)
            tf.close()

    def _execute_conf_command(self, root):
        if self.postcmd:
            root.su().post_root_command()

    # run as root
    def post_command(self):
        return self.postcmd

    # run as root
    def setarch_command(self, from_, to):
        cmd = []
        found = self.archmap.get(to)
        if found:
            cmd.extend(found)
        return cmd

    def _root_arch(self, packagemanager):
        if self.arch == "host":
            arch = packagemanager.system_arch()
        else:
            arch = self.arch
        return arch

    def _latest_link_name(self, interactive):
        username, _ = my_username()
        if interactive:
            suffix = self.latestsuffix_interactive
        else:
            suffix = self.latestsuffix_build
        name = username + suffix
        return name

    def _latest_path(self, interactive):
        return os.path.join(self.topdir, self._latest_link_name(interactive))

    def _update_latest_link(self, state, rootpath, interactive=False):
        rootname = os.path.basename(rootpath)
        # creates a relative link pointing to statename/rootid
        rootsubdir = self._root_path(state, rootname)
        comps = os.path.abspath(rootsubdir).rsplit(os.path.sep, 2)
        relative = os.path.sep.join(comps[-2:])
        util.replace_link(self._latest_path(interactive), relative)

    def _resolve_latest_link(self, interactive=False, fail=True):
        kind = ("build", "interactive")[interactive]
        linkpath = self._latest_path(interactive)
        try:
            if not os.path.lexists(linkpath):
                logger.debug("latest link %s was not found", linkpath)
                raise ChrootError, ("no information about the latest root "
                         "was found")
            try:
                target = os.readlink(linkpath)
            except EnvironmentError, e:
                raise ChrootError, "failed to read latest link: %s" % (e)
            logger.debug("latest link (%s) points to %s", kind, target)
            # expects a link pointing to statename/rootid
            fields = target.rsplit(os.path.sep, 2)
            if len(fields) < 2:
                raise ChrootError, "invalid path name linked by %s" % (linkpath)
            statename = fields[-2]
            path = os.path.join(self.topdir, target)
            if not os.path.exists(path):
                raise ChrootError, ("it appears the latest root does not "
                        "exist anymore: %s" % (path))
            return self._dir_to_state(statename), path
        except ChrootError, e: # goto FTW!!
            if fail:
                raise
            logger.debug("failed to resolve the latest (%s) link: %s",
                    kind, e)
            return None, None

    def _state_path(self, dir, name):
        return os.path.join(self.topdir, dir, name)

    def _root_path(self, state, name):
        return self._state_path(self._state_to_dir(state), name)

    def _active_path(self, name):
        return self._state_path(self.activestatedir, name)

    def _temp_path(self, name):
        return self._state_path(self.tempstatedir, name)

    def _keep_path(self, name):
        return self._state_path(self.keepstatedir, name)

    def _old_path(self, name):
        return self._state_path(self.oldstatedir, name)

    def _state_to_dir(self, state):
        return STATE_NAMES[state]

    def _dir_to_state(self, dirname):
        return STATE_DIRS[dirname]

    def _existing_root(self, name, required=False, interactive=False):
        if name == "latest":
            state_and_path = self._resolve_latest_link(interactive)
        else:
            statedirs = ((Active, self._active_path(name)),
                    (Keep, self._keep_path(name)),
                    (Old, self._old_path(name)),
                    (Temp, self._temp_path(name)))
            for state, dir in statedirs:
                if os.path.exists(dir):
                    state_and_path = state, dir
                    break
            else:
                if required:
                    raise ChrootError, "root not found: %s" % (name)
                state_and_path = None, None
        return state_and_path

    def _check_state_dirs(self):
        for m in (self._active_path, self._temp_path, self._keep_path,
                self._old_path):
            statepath = m("") # "" appends nothing after state path
            if not os.path.exists(statepath):
                raise ChrootError, "missing roots directory: %s" % (statepath)

    def _check_new_root_name(self, name, forcenew=False):
        if "/" in name or name == "latest":
            raise ChrootError, "invalid root name: %s" % (name)
        state, path = self._existing_root(name)
        if state is not None and (state is not Temp and forcenew):
            raise ChrootError, ("the root name %s conflicts with existing "
                    "root at %s" % (name, path))

    def create_new(self, name, packagemanager, repos, logger,
            interactive=False, forcenew=False):
        self._check_new_root_name(name, forcenew)
        path = self._temp_path(name)
        self.su().mkdir(path)
        self.su().create_devs(path)
        packagemanager.create_root(self.suwrapper, repos, path, logger,
                interactive)
        arch = self._root_arch(packagemanager)
        chroot = Chroot(self, path, arch, interactive=interactive)
        self._create_metadata_files(chroot, interactive)
        self._copy_files_from_conf(chroot)
        self._execute_conf_command(chroot)
        return chroot

    def _move_root(self, root, dest):
        rootparent = os.path.dirname(root.path)
        if not util.same_partition(rootparent, dest):
            raise RootError, ("%s and %s must be on the same partition" %
                    (rootparent, dest))
        logger.debug("moving root from %s to %s", root.path, dest)
        self.su().rename(root.path, dest)
        root.path = dest

    def _is_interactive(self, rootpath):
        checkpath = os.path.abspath(rootpath + os.path.sep +
                self.interactivefile)
        if os.path.exists(checkpath):
            logger.debug("found: %s", checkpath)
            return True
        return False

    def _keep_file(self, rootpath):
        return os.path.abspath(rootpath + os.path.sep + self.keepfile)

    def _marked_as_keep(self, rootpath):
        checkpath = self._keep_file(rootpath)
        if os.path.exists(checkpath):
            logger.debug("marked as keep: %s", checkpath)
            return True
        return False

    def _keep_root(self, root):
        """Mark a given root path as 'keep'

        So that we can move it back to 'keep' after activating it.
        """
        from tempfile import NamedTemporaryFile
        tf = NamedTemporaryFile()
        tf.write("keep\n")
        tf.flush()
        root.copy_in(tf.name, self.keepfile)
        tf.close()

    def activate_root(self, root):
        if root.state != Active:
            self._check_state_dirs()
            name = os.path.basename(root.path)
            dest = self._active_path(name)
            self._move_root(root, dest)
            root.state = Active
            self._update_latest_link(root.state, root.path,
                    root.interactive)

    def deactivate_root(self, root):
        if root.state != Old:
            self._check_state_dirs()
            name = os.path.basename(root.path)
            state, _ = self._existing_root(name)
            if state == Active:
                # else: the root has been moved by someone else, just
                # forget about moving
                if self._marked_as_keep(root.path):
                    dest = self._keep_path(name)
                    newstate = Keep
                else:
                    dest = self._old_path(name)
                    newstate = Old
                self._move_root(root, dest)
                root.state = newstate
                self._update_latest_link(root.state, root.path,
                        root.interactive)

    def get_root_by_name(self, name, packagemanager, interactive=DontCare):
        state, path = self._existing_root(name, interactive=interactive,
                required=True)
        arch = self._root_arch(packagemanager)
        chroot = Chroot(self, path, arch, state, interactive)
        chroot.interactive = self._is_interactive(chroot.path)
        if interactive is not DontCare and \
                (interactive and not chroot.interactive):
            raise RootError, ("the root %s is not prepared for "
                    "interactive use" % (name))
        elif not interactive and chroot.interactive:
            raise RootError, ("the root %s is prepared for "
                    "interactive use" % (name))
        return chroot

    def _list_chroots(self, states=(Active, Old, Keep)):
        _, intlatest = self._resolve_latest_link(interactive=True,
                fail=False)
        _, buildlatest = self._resolve_latest_link(interactive=False,
                fail=False)
        for state in states:
            path = self._root_path(state, "") # duh!
            if os.path.exists(path):
                try:
                    names = os.listdir(path)
                except EnvironmentError, e:
                    logger.warn("failed to list directory: %s", e)
                else:
                    for name in names:
                        rootpath = os.path.abspath(os.path.join(path, name))
                        if (not name.startswith(".") and
                                os.path.isdir(rootpath)):
                            interactive = self._is_interactive(rootpath)
                            latest = (intlatest == rootpath
                                    or buildlatest == rootpath)
                            kind = ("build", "interactive")[interactive]
                            statename = STATE_NAMES[state]
                            yield name, rootpath, kind, statename, latest

    def list_roots(self):
        for name, rootpath, kind, state, latest in self._list_chroots():
            yield name, kind, state, latest

    def guess_target_name(self, name, interactive=False):
        found = None
        state, path = self._existing_root(name, interactive=interactive)
        if path is not None:
            confpath = os.path.abspath(path + os.path.sep +
                    self.targetfile)
            if os.path.exists(confpath):
                logger.debug("reading %s to guess target name", confpath)
                try:
                    with open(confpath) as f:
                        found = f.readline().strip()
                except EnvironmentError, e:
                    logger.warn("cannot read target information "
                            "inside chroot on %s: %s" % (confpath, e))
        return found

    def destroy(self, root, interactive):
        if root.state is not Old:
            raise RootError, ("cannot destroy a root that is still "
                    "active: %s" % (root.path))
        self.su().destroy_root(root.path)
        _, latestpath = self._resolve_latest_link(interactive, fail=False)
        if os.path.abspath(root.path) == latestpath:
            lpath = self._latest_path(interactive)
            logger.debug("removing -latest link as the pointed root was "
                    "destroyed: %s", lpath)
            try:
                os.unlink(lpath)
            except EnvironmentError, e:
                logger.warn("failed to remove the latest link: %s" % (e))

    def is_old(self, timestamp):
        age = time.time() - timestamp
        return age > self.maxrootage

    def clean(self, dry_run=False):
        for name, rootpath, _, _, latest in self._list_chroots(states=(Old,)):
            try:
                timestamp = os.stat(rootpath).st_ctime
            except EnvironmentError, e:
                logger.error("failed to stat the directory %s: %s" %
                        (rootpath, e))
                continue
            if self.is_old(timestamp):
                if latest:
                    logger.debug("root %s is old, but is marked as "
                            "'latest' and will not be removed", rootpath)
                else:
                    logger.debug("root at %s has timestamp %s and will be "
                            "destroyed", rootpath, timestamp)
                    yield name, timestamp
                    if not dry_run:
                        self.su().destroy_root(rootpath)

    def keep(self, id, packagemanager):
        root = self.get_root_by_name(id, packagemanager)
        if root.state is Keep:
            logger.info("%s is already marked as 'keep'", id)
        else:
            self._keep_root(root)
            if root.state != Active:
                dest = self._keep_path(id)
                self._move_root(root, dest)
                root.state = Keep

    def root_path(self, id, interactive=True):
        state, path = self._existing_root(id, interactive=interactive)
        return path

    def test_sudo(self, interactive=True):
        self.su().test_sudo(interactive)

    # executed as root:
    def check_valid_subdir(self, path):
        abstop = os.path.abspath(self.topdir) + "/"
        abspath = os.path.abspath(path) + "/"
        if not abspath.startswith(abstop):
            raise RootError, "path must be inside %s" % (abstop)

    # executed as root:
    def check_valid_outdir(self, path):
        absdone = os.path.abspath(self.donedir) + "/"
        absfail = os.path.abspath(self.faildir) + "/"
        abspath = os.path.abspath(path)
        if (not abspath.startswith(absdone) and not
                abspath.startswith(absfail)):
            raise RootError, ("path must be inside %s or %s" %
                    (self.donedir, self.faildir))

    # run as root
    def allows_interactive_shell(self):
        return self.allowshell

    # run as root
    def mount_points(self):
        for mountinfo in self.mountpoints:
            yield mountinfo
        for bindinfo in self.binds:
            yield bindinfo[0], bindinfo[1], "bind", None

    # run as root
    def devices(self):
        return self.devs[:]

class CachedManagerMixIn:

    def _cache_base_path(self, interactive):
        name = self.targetname
        if interactive:
            name += "-interactive"
        else:
            name += "-build"
        return os.path.join(self.topdir, name)

    def _cache_path(self, interactive):
        return self._cache_base_path(interactive)

    def invalidate(self, interactive=DontCare):
        if interactive is DontCare:
            modes = [True, False]
        else:
            modes = [interactive]
        for mode in modes:
            cachepath = self._cache_path(interactive=mode)
            if os.path.exists(cachepath):
                self.su().destroy_root(cachepath)

class CompressedChrootManager(CachedManagerMixIn, ChrootRootManager):

    @classmethod
    def load_config(class_, suwrapper, rootconf, globalconf):
        names = ChrootRootManager.load_config(suwrapper, rootconf,
                globalconf)
        names.update(
                dict(compress_command=shlex.split(rootconf.chroot_compress_command),
                    decompress_command=shlex.split(rootconf.chroot_decompress_command),
                    targetname=rootconf.target_name,
                    cachedir=rootconf.chroot_cache_dir,
                    cacheext=rootconf.chroot_cache_ext))
        return names

    def __init__(self, compress_command, decompress_command, cachedir,
            cacheext, targetname, *args, **kwargs):
        super(CompressedChrootManager, self).__init__(*args, **kwargs)
        self.compress_command = compress_command
        self.decompress_command = decompress_command
        self.cachedir = cachedir
        self.cacheext = cacheext
        self.targetname = targetname

    def _run(self, args, stdout=None, stdin=None):
        if stdout is None:
            stdout = subprocess.PIPE
        try:
            proc = subprocess.Popen(args=args, shell=False, stdout=stdout,
                    stdin=stdin, stderr=subprocess.PIPE)
        except EnvironmentError, e:
            raise RootError, "failed to run command %s: %s" % (e)
        proc.wait()
        if proc.returncode != 0:
            cmdline = subprocess.list2cmdline(args)
            output = proc.stderr.read()
            raise RootError, ("command failed:\n%s\n%s" % (cmdline,
                output))

    def _cache_path(self, interactive):
        return self._cache_base_path(interactive) + self.cacheext


    def create_new(self, name, packagemanager, repos, logstore,
            interactive=False):
        self._check_new_root_name(name)
        cachepath = self._cache_path(interactive)
        if not os.path.exists(cachepath):
            logger.debug("%s not found, creating new root" % (cachepath))
            if not os.path.exists(self.cachedir):
                self.su().mkdir(self.cachedir)
            chroot = ChrootRootManager.create_new(self, name,
                    packagemanager, repos, logstore, interactive)
            # suwrapper already takes care of temporary naming
            logger.debug("compressing %s into %s" % (chroot.path,
                cachepath))
            self.suwrapper.compress_root(chroot.path, cachepath)
        else:
            path = self._root_path(Temp, name)
            self.su().mkdir(path)
            chroot = Chroot(self, path, self._root_arch(packagemanager),
                    interactive=interactive)
            logger.debug("decompressing %s into %s" % (cachepath, path))
            self.suwrapper.decompress_root(cachepath, path)
        return chroot

    # run as root
    def root_compress_command(self, root, tarfile):
        return self.compress_command + [tarfile, "-C", root, "."]

    # run as root
    def root_decompress_command(self, root, tarfile):
        return self.decompress_command + [tarfile, "-C", root, "."]

class TmpfsChrootManager(CompressedChrootManager):

    @classmethod
    def load_config(class_, suwrapper, rootconf, globalconf):
        names = super(TmpfsChrootManager, class_).load_config(suwrapper,
                rootconf, globalconf)
        mountcmd = shlex.split(rootconf.tmpfs_mount_command)
        umountcmd = shlex.split(rootconf.tmpfs_umount_command)
        names.update(dict(mountcmd=mountcmd, umountcmd=umountcmd))
        return names

    def __init__(self, mountcmd, umountcmd, *args, **kwargs):
        super(TmpfsChrootManager, self).__init__(*args, **kwargs)
        self.mountcmd = mountcmd
        self.umountcmd = umountcmd

    def _root_path(self, state, name):
        "Always returns roots inside the 'active' state"
        return self._state_path(self.activestatedir, name)

    def get_root_by_name(self, *args, **kwargs):
        raise ChrootError, ("the root type chroot-with-tmpfs never allows "
                "using an existing root")

    def create_new(self, name, packagemanager, repos, logstore,
            interactive=False):
        rootpath = self._root_path(Tmpfs, name)
        try:
            exists = os.path.exists(rootpath)
        except EnvironmentError, e:
            raise ChrootError, ("failed to verify if directory %s "
                    "exists: %s" % (rootpath, e))
        if not exists:
            self.su().mkdir(rootpath)
        self.su().mount_tmpfs(rootpath)
        return super(TmpfsChrootManager, self).create_new(name,
                packagemanager, repos, logstore, interactive)

    def activate_root(self, root):
        "Nothing to do"

    def deactivate_root(self, root):
        self.su().umount_tmpfs(root.path)

    def destroy(self, root, interactive):
        "Nothing to do"

    # run as root
    def mount_root_command(self, path):
        cmd = self.mountcmd[:]
        cmd.append(path)
        return cmd

    # run as root
    def umount_root_command(self, path):
        cmd = self.umountcmd[:]
        cmd.append(path)
        return cmd

class BtrfsChrootManager(CachedManagerMixIn, ChrootRootManager):

    @classmethod
    def load_config(class_, suwrapper, rootconf, globalconf):
        names = ChrootRootManager.load_config(suwrapper, rootconf,
                globalconf)
        newsvcmd = shlex.split(rootconf.btrfs_create_subvol_command)
        snapsvcmd = shlex.split(rootconf.btrfs_snapshot_subvol_command)
        delsvcmd = shlex.split(rootconf.btrfs_delete_subvol_command)
        targetname = rootconf.target_name
        names.update(
                dict(newsvcmd=newsvcmd,
                    snapsvcmd=snapsvcmd,
                    delsvcmd=delsvcmd,
                    targetname=targetname))
        return names

    def __init__(self, newsvcmd, snapsvcmd, delsvcmd, targetname, *args,
            **kwargs):
        super(BtrfsChrootManager, self).__init__(*args, **kwargs)
        self.newsvcmd = newsvcmd
        self.snapsvcmd = snapsvcmd
        self.delsvcmd = delsvcmd
        self.targetname = targetname
        self.destroycmd = delsvcmd

    def create_new(self, name, packagemanager, repos, logstore,
            interactive=False):
        self._check_new_root_name(name)
        templatepath = self._cache_base_path(interactive)
        rootpath = self._root_path(Temp, name)
        if not os.path.exists(templatepath):
            self.su().btrfs_create(rootpath)
            root = ChrootRootManager.create_new(self, name,
                    packagemanager, repos, logstore, interactive,
                    forcenew=True)
            self.su().btrfs_snapshot(rootpath, templatepath)
        else:
            self.su().btrfs_snapshot(templatepath, rootpath)
            root = Chroot(self, rootpath, self._root_arch(packagemanager),
                    interactive=interactive)
        return root

root_managers = Registry("root type")
root_managers.register("chroot", ChrootRootManager)
root_managers.register("chroot-with-cache", CompressedChrootManager)
root_managers.register("chroot-with-btrfs", BtrfsChrootManager)
root_managers.register("chroot-with-tmpfs", TmpfsChrootManager)

def get_root_manager(suwrapper, rootconf, globalconf):
    klass_ = root_managers.get_class(rootconf.root_type)
    instance = klass_(**klass_.load_config(suwrapper, rootconf, globalconf))
    return instance
