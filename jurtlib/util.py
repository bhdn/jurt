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

logger = logging.getLogger("jurt.util")

def replace_link(linkpath, linkdest):
    if os.path.lexists(linkpath):
        if not os.path.islink(linkpath):
            newname = linkpath + "." + str(int(time.time()))
            logger.warn("%s already exists and it is not a symlink "
                    "as expected, renaming it to %s" % (linkpath,
                        newname))
            os.move(linkpath, newname)
        else:
            logger.debug("removing existing link %s" % (linkpath))
            os.unlink(linkpath)
    logger.debug("creating link %s pointing to %s" % (linkpath, linkdest))
    os.symlink(linkdest, linkpath)

def node_dev(path):
    if not os.path.exists(path):
        path = os.path.dirname(path)
    st = os.stat(path)
    return st.st_dev

def same_partition(one, other):
    return node_dev(one) == node_dev(other)
