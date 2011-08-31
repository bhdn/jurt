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
import logging

logger = logging.getLogger("jurt.spool")

class Spool:

    def __init__(self, path, packagemanager):
        self.path = path
        self.packagemanager = packagemanager

    def create_dirs(self):
        if not os.path.exists(self.path):
            os.makedirs(self.path)
        self._update()

    def _update(self):
        self.packagemanager.update_repository_metadata(self.path)

    def package_count(self):
        return sum(1 for name in os.listdir(self.path)
                if self.packagemanager.valid_binary(name))

    def put_packages(self, paths):
        spoolpaths = []
        for path in paths:
            if self.packagemanager.valid_binary(path):
                dest = os.path.join(self.path, os.path.basename(path))
                spoolpaths.append(dest)
                logger.debug("creating hardlink from %s to %s" % (path, dest))
                os.link(path, dest)
            else:
                logger.debug("not copying %s to the spool at %s" % (path,
                    self.path))
        self._update()
        return spoolpaths
