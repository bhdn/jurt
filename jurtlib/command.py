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
import sys
import os
import optparse
import logging
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
