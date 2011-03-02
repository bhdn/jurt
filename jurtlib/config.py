import os
from cStringIO import StringIO
import logging
import ConfigParser

from jurtlib import log, defaults, Error

log = logging.getLogger("jurt.config")

class ConfigError(Error):
    pass

def parse_bool(raw):
    raw = raw.strip().lower()
    if raw in ("yes", "true"):
        return True
    else:
        return False

class SectionWrapper(object):

    _config = None
    _section = None

    def __init__(self, parent, section, defaultssec=None):
        self._config = parent.config_object()
        self._parent = parent
        self._section = section
        self._defaultssec = defaultssec

    def __getattr__(self, name):
        try:
            return self._config.get(self._section, name)
        except ConfigParser.NoOptionError:
            try:
                nicename = name.replace("_", "-")
                return self._config.get(self._section, nicename)
            except (AttributeError, ConfigParser.NoOptionError):
                if self._defaultssec is not None:
                    return getattr(self._defaultssec, name)
                else:
                    raise

    def __setattr__(self, name, value):
        if name.startswith("_"):
            object.__setattr__(self, name, value)
        else:
            self._config.set(self._section, name, value)

class BaseWrapper(SectionWrapper):

    def __getattr__(self, name):
        pass

class Config:

    _section = None
    _config = None
    _sections = {}

    def __init__(self):
        self._config = ConfigParser.ConfigParser()
        self.parse(defaults.CONFIG_DEFAULTS)

    def config_object(self):
        return self._config

    def __repr__(self):
        output = StringIO()
        self._config.write(output)
        return output.getvalue()

    def __getattr__(self, name):
        try:
            section = self._sections[name]
        except KeyError:
            try:
                # configuration-names-look-better-using-dashes-than
                # underscores_that_look_like_a_programming_mindset_leak
                nicename = name.replace("_", "-")
                section = self._sections[nicename]
            except KeyError:
                if name not in self._config.sections():
                    raise AttributeError, name
                section = SectionWrapper(self, name)
                self._sections[name] = section
        return section

    def get_section(self, name, defaultsname=None):
        return SectionWrapper(self, name, getattr(self, defaultsname))

    def merge(self, data):
        for section, values in data.iteritems():
            for name, value in values.iteritems():
                self._config.set(section, name, value)

    def parse(self, raw):
        self._config.readfp(StringIO(raw))

    def load(self, path):
        self._config.readfp(open(path))


class JurtConfig(Config):
    
    def targets(self):
        # looks for [target somename] sections
        for name in self._config.sections():
            fields = name.split()
            if len(fields) > 1 and fields[0] == "target":
                targetconf = self.get_section(name, "any target")
                targetconf.target_name = fields[1]
                yield (fields[1], targetconf)
