import tests
from os.path import join

from jurtlib.config import JurtConfig
from jurtlib.su import JurtRootWrapper

class TestJurtRootWrapper(tests.Test):

    def _get_wrapper(self):
        config, sections = self.sample_config()
        suconf = sections[0][1]
        suconf.sudo_command = join(self.rootdir, "fake_su_wrapper.py")
        su = JurtRootWrapper("first", suconf, config)
        return su

    def test_create_wrapper(self):
        su = self._get_wrapper()

    def test_adduser(self):
        su = self._get_wrapper()
        su.test_sudo()
