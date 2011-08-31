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
import time
import logging
from jurtlib.registry import Registry

logger = logging.getLogger("jurt.logger")

class LoggerFactory:

    @classmethod
    def load_config(class_, loggerconf, globalconf):
        logbasedir = os.path.expanduser(loggerconf.logs_dir)
        return dict(logbasedir=logbasedir)

    def __init__(self, logbasedir):
        self.logbasedir = logbasedir

    def get_logger(self, id, outputfile=None):
        return Logger(id, self.logbasedir, outputfile=outputfile)

class OutputLogger(file):

    def __init__(self, name, mode="a", trap=None, outputfile=None):
        super(OutputLogger, self).__init__(name, mode)
        self.trap = trap
        self.outputfile = outputfile
        self.matches = []

    def start(self):
        self.write("==== started log at %s\n" % (time.ctime()))
        self.flush()

    def write(self, data):
        file.write(self, data)
        if self.trap is not None:
            found = list(self.trap.finditer(data))
            if found:
                self.matches.extend(found)
        if self.outputfile is not None:
            self.outputfile.write(data)

    def close(self):
        self.write("==== closing log at %s\n" % (time.ctime()))
        self.flush()
        file.close(self)

    def location(self):
        return self.name

class Logger:

    def __init__(self, id, logbasedir, outputfile=None):
        self.id = id
        self.path = os.path.join(logbasedir, id)
        self.subpackages = []
        self.logfiles = []
        self.outputfile = outputfile
        if not os.path.exists(self.path):
            os.makedirs(self.path)

    def get_output_handler(self, name, trap=None):
        path = os.path.join(self.path, name) + ".log"
        fileobj = OutputLogger(path, trap=trap, outputfile=self.outputfile)
        logger.debug("created log file %s" % (path))
        fileobj.start()
        self.logfiles.append(path)
        return fileobj

    def done(self):
        pass

    def logs(self):
        found = []
        for subid, pkg in self.subpackages:
            for path in pkg.logfiles:
                found.append((subid, path))
        return self.id, found

    def subpackage(self, subid):
        logger = Logger(subid, self.path, outputfile=self.outputfile)
        self.subpackages.append((subid, logger))
        return logger

loggers = Registry("logger type")
loggers.register("default", LoggerFactory)

def get_logger_factory(loggerconf, globalconf):
    klass = loggers.get_class(loggerconf.logger_type)
    return klass(**klass.load_config(loggerconf, globalconf))
