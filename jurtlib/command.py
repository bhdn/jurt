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
import optparse
import logging
import time
from jurtlib import Error
from jurtlib.config import JurtConfig
from jurtlib.facade import JurtFacade

class CliError(Error):
    pass

class DontGetInTheWayFormatter(optparse.IndentedHelpFormatter):
    """Class only intended to go around the crappy text wrapper"""

    def format_description(self, description):
        if not description.endswith("\n"):
            return description + "\n"
        return description

class JurtCommand(object):

    descr = "The base jurt command."
    usage = "[options] [args]"

    def create_parser(self):
        parser = optparse.OptionParser(formatter=DontGetInTheWayFormatter())
        return parser

    def init_parser(self, parser):
        def parse_option(option, opt_str, value, parser, *args, **kwargs):
            kv = value.split("=", 1)
            if len(kv) != 2:
               raise optparse.OptionValueError, "-o accepts values only in "\
                       "the name=value form"
            levels = kv[0].split(".")
            lastv = kv[1]
            for name in levels[:0:-1]:
                lastv = {name: lastv}
            if levels[0] in parser.values.config_options:
                parser.values.config_options[levels[0]].update(lastv)
            else:
                parser.values.config_options[levels[0]] = lastv
        parser.set_usage(self.usage)
        parser.set_description(self.descr)
        parser.set_defaults(config_options={})
        parser.add_option("-v", "--verbose", action="store_true", default=False)
        parser.add_option("-q", "--quiet", action="store_true", default=False)
        parser.add_option("-o", "--option", type="string", action="callback",
                callback=parse_option,
                help="set one configuration option in the form opt=val")

    def parse_args(self, parser, args):
        return parser.parse_args(args)

    def create_config(self):
        config = JurtConfig()
        return config

    def update_config(self, config, opts, args):
        config.merge(opts.config_options)

    def config_files(self, config):
        if os.path.exists(config.conf.system_file):
            yield config.conf.system_file
        envconf = os.getenv(config.conf.path_environment)
        if envconf is not None and os.path.exists(envconf):
            yield envconf
        userconf = os.path.expanduser(config.conf.user_file)
        if os.path.exists(userconf):
            yield userconf

    def load_config_files(self, config):
        for path in self.config_files(config):
            config.load(path)

    def setup_logging(self, config, opts, args):
        if opts.verbose:
            level = logging.DEBUG
        elif opts.quiet:
            level = logging.WARN
        else:
            level = logging.INFO
        # had to change the syntax in order to not conflict with
        # configparser
        format = config.jurt.log_format.replace("$", "%")
        logging.basicConfig(level=level, format=format)

    def run(self, tasks):
        print "Done."

    def main(self):
        try:
            parser = self.create_parser()
            config = self.create_config()
            self.init_parser(parser)
            opts, args = self.parse_args(parser, sys.argv[1:])
            self.load_config_files(config)
            self.update_config(config, opts, args)
            self.setup_logging(config, opts, args)
            jurt = JurtFacade(config)
            self.config = config
            self.opts = opts
            self.args = args
            self.jurt = jurt
            self.run()
        except Error, e:
            sys.stderr.write("error: %s\n" % (e))
            sys.exit(2)
        except KeyboardInterrupt:
            sys.stderr.write("interrupted\n")

class Shell(JurtCommand):

    usage = "%prog -t TARGET [-l] [-i|-n root-id]"
    descr = """\
Creates a root and drops into a shell.

(Notice you can also use jurt-build --stop)
"""

    def init_parser(self, parser):
        JurtCommand.init_parser(self, parser)
        parser.add_option("-t", "--target", type="string",
                help="Target root name (jurt-list-targets for a list)")
        parser.add_option("-i", "--id", default=None,
                help=("Enter in an (supposedly) existing root named "
                    "ID (see -l)"))
        parser.add_option("-l", "--latest", default=False,
                action="store_true",
                help="Use the latest created root")
        parser.add_option("-n", "--newid", default=None, metavar="ID",
                help=("Set the name of the root to be created "
                    "(so that it can be reused with -i ID)"))

    def run(self):
        if sum((self.opts.latest, bool(self.opts.id),
                bool(self.opts.newid))) > 1:
            raise CliError, "-i, -n and -l cannot be used together"
        fresh = True
        id = None
        if self.opts.id:
            fresh = False
            id = self.opts.id
        if self.opts.latest:
            id = "latest"
            fresh = False
        elif self.opts.newid:
            id = self.opts.newid
        # else: fresh = True
        self.jurt.shell(self.opts.target, id, fresh)

class Build(JurtCommand):

    usage = "%prog -t TARGET file.src.rpm..."
    descr = """Builds a set of packages

Built packages will be added into a temporary repository so that they can
be used as build dependencies by those that are processed afterwards.

To list the targets, use jurt-list-targets.

To see the configuration used by jurt, use jurt-showrc.

Also, jurt-root-command should be able to use sudo for running commands as
root. Run jurt-test-sudo for checking whether it is properly configured.
"""

    def init_parser(self, parser):
        JurtCommand.init_parser(self, parser)
        parser.add_option("-t", "--target", type="string",
                help="Target packages are built for")
        parser.add_option("-b", "--stop", default=None, metavar="STAGE",
                help="Stop at build stage STAGE and drops into a shell")
        parser.add_option("-s", "--showlog",
                action="store_true", default=False,
                help="Show the (also logged) output of build process")
        parser.add_option("-k", "--keeproot", default=False,
                action="store_true",
                help="Do not remove the root after build (useful to use "
                    "with -l)")
        parser.add_option("-i", "--id", default=None,
                help=("Enter in an (supposedly) existing root named "
                    "ID (see -l)"))
        parser.add_option("-l", "--latest", default=False,
                action="store_true",
                help=("Use the latest created root (when -k is used "
                      "beforehand)"))
        parser.add_option("-K", "--keep-building", default=False,
                action="store_true",
                help=("Keep building the following packages when the "
                    "preceding one has failed (jurt aborts by default)."))
        parser.add_option("-n", "--newid", default=None, metavar="ID",
                help=("Set the name of the root to be created "
                    "(so that it can be reused with -i ID)"))
        parser.add_option("-d", "--duration", default=None, type="int",
                metavar="SECS",
                help=("Limit in seconds of build time (when exceeded the "
                     "build task is killed with SIGTERM)"))

    def run(self):
        if not self.args:
            raise CliError, "no source packages provided (--help?)"
        if self.opts.showlog:
            outputfile = sys.stdout
        else:
            outputfile = None
        if sum((self.opts.latest, bool(self.opts.id),
                bool(self.opts.newid))) > 1:
            raise CliError, "-i, -n and -l cannot be used together"
        fresh = True
        id = None
        if self.opts.id:
            fresh = False
            id = self.opts.id
        if self.opts.latest:
            id = "latest"
            fresh = False
        elif self.opts.newid:
            id = self.opts.newid
        # else: fresh = True
        self.jurt.build(self.args, self.opts.target, id, fresh,
                timeout=self.opts.duration, stage=self.opts.stop,
                outputfile=outputfile, keeproot=self.opts.keeproot,
                keepbuilding=self.opts.keep_building)

class Clean(JurtCommand):

    usage = "%prog -t TARGET file.src.rpm..."
    descr = "Cleans old roots"

    def init_parser(self, parser):
        JurtCommand.init_parser(self, parser)
        parser.add_option("-n", "--dry-run", default=False,
            action="store_true",
            help="Do not remove any root")

    def run(self):
        for name, timestamp in self.jurt.clean(dry_run=self.opts.dry_run):
            age = (time.time() - timestamp) // 24 // 60 // 60
            print "removing %s (%d days)" % (name, age)


class Invalidate(JurtCommand):

    usage = "%prog [TARGET]"
    descr = """\
Cleans the root cache for a given build target.

In case the target name is ommited, the default build target will be used.

Use jurt list-targets to enumerate the targets available.
"""

    def run(self):
        if not self.args:
            self.jurt.invalidate(None)
        else:
            for targetname in self.args:
                self.jurt.invalidate(targetname)

class Keep(JurtCommand):

    descr = "Mark a given root to not be destroyed by jurt-clean"
    usage = "%prog <rootname>..."

    def init_parser(self, parser):
        JurtCommand.init_parser(self, parser)

    def run(self):
        if not self.args:
            raise CliError, "you must supply a root name"
        for id in self.args:
            self.jurt.keep(id)


class ListRoots(JurtCommand):

    descr = """\
Lists roots available to be used on jurt-shell -i <ID>

The output is in the format FLAGS NAME.

FLAGS can be:

 b      indicates that it was used for non-interactive build (and thus
        can only be reused for that purpuse)
 i      it can be used for interactive build or shell (jurt-build -b or
        jurt-shell)
 k      the root is marked to not be destroyed by jurt-clean
 o      the root is not used and can be destroyed
 a      the root is active
 l      the root can be referred with -l on the commands that support this
        option.
"""

    def init_parser(self, parser):
        JurtCommand.init_parser(self, parser)

    def run(self):
        for name, kind, state, latest in self.jurt.list_roots():
            flag = kind[0] + state[0]
            if latest:
                flag += "l"
            print "%s\t%s" % (flag, name)

class ListTargets(JurtCommand):

    descr = "List all build targets"

    def run(self):
        for target, default in self.jurt.target_names():
            if default:
                print target, "(default)"
            else:
                print target


class Pull(JurtCommand):

    descr = """\
Copies all files inside SPECS and SOURCES inside a root to a given
destination directory. If the destination directory is omitted it will use
the current directory.

/!\\ WARNING: it overwrites any existing file in the destination directory!
"""
    usage = "%prog [opts] [DESTDIR]"

    def init_parser(self, parser):
        JurtCommand.init_parser(self, parser)
        parser.add_option("-t", "--target", type="string",
                help="Target rooot name (jurt-list-targets for a list)")
        parser.add_option("-p", "--preserve", default=False,
                action="store_true",
                help="Do not overwrite any existing files")
        parser.add_option("-n", "--dry-run", default=False,
                action="store_true",
                help="Only list files to be copied")
        parser.add_option("-i", "--id", default=None,
                help=("Enter in an (supposedly) existing root named "
                    "ID (see -l)"))
        parser.add_option("-l", "--latest", default=True,
                action="store_true",
                help="Use the latest created root (default)")

    def run(self):
        if self.opts.id:
            id = self.opts.id
        else:
            id = "latest"
        if self.args:
            dest = self.args[0]
        else:
            dest = "."
        for path, dstpath in self.jurt.pull(self.args,
                targetname=self.opts.target, id=id, dest=dest,
                overwrite=not self.opts.preserve,
                dryrun=self.opts.dry_run):
            print dstpath

class Put(JurtCommand):

    descr = "Copies files into a root"
    usage = "%prog [opts] FILES.."

    def init_parser(self, parser):
        JurtCommand.init_parser(self, parser)
        parser.add_option("-t", "--target", type="string",
                help="Target rooot name (jurt-list-targets for a list)")
        parser.add_option("-i", "--id", default=None,
                help=("Enter in an (supposedly) existing root named "
                    "ID (see -l)"))
        parser.add_option("-l", "--latest", default=True,
                action="store_true",
                help="Use the latest created root (default)")

    def run(self):
        if not self.args:
            raise CliError, "you must provide some files to be copied"
        if self.opts.id:
            id = self.opts.id
        else:
            id = "latest"
        self.jurt.put(self.args, targetname=self.opts.target, id=id)

class TestSudo(JurtCommand):

    descr = "Checks if jurt is properly setup"

    def run(self):
        for status in self.jurt.check_permissions():
            print status

# jurt-root-command also would be here, hadn't it been that ugly
# jurt-setup too
