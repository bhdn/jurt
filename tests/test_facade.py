import tests

from jurtlib.config import JurtConfig
from jurtlib.facade import JurtFacade

class TestFacade(tests.Test):
    
    def test_create_facade(self):
        config = JurtConfig()
        facade = JurtFacade(config)

