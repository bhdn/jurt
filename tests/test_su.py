import tests

from jurtlib.config import JurtConfig
from jurtlib.su import JurtRootWrapper

class TestJurtRootWrapper(tests.Test):

    def test_create_wrapper(self):
        config, sections = self.sample_config()
        suconf = sections[0][1]
        su = JurtRootWrapper("first", suconf, config)
