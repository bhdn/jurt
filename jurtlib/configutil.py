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
import shlex
import logging

logger = logging.getLogger("jurtlib.configutil")

def parse_conf_fields(rawvalue, nofields, name):
    entries = []
    for rawentry in rawvalue.split("|"):
        if rawentry:
            fields = shlex.split(rawentry)
            if len(fields) != nofields:
                logger.warn("expected %d fields in %s "
                        "entry: %s", nofields, name, rawentry)
            else:
                entries.append(fields)
    return entries

def parse_bool(raw):
    raw = raw.strip().lower()
    if raw in ("yes", "true"):
        return True
    else:
        return False

