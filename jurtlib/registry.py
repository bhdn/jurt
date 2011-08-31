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
from jurtlib import Error

class Registry:
    register = dict.__setitem__

    def __init__(self, description):
        self._classes = {}
        self.description = description

    def register(self, name, class_):
        self._classes[name] = class_

    def get_instance(self, name, *args, **kwargs):
        class_ = self.get_class(name)
        instance = class_(*args, **kwargs)
        return instance

    def get_class(self, name):
        try:
            class_ = self._classes[name]
        except KeyError:
            raise Error, "no such %s: %s" % (self.description, name)
        return class_
