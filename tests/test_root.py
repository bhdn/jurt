import tests

from jurtlib.root import Root, RootManager

class TestRootABC(tests.Test):

    def test_instantiate_abc(self):
        self.assertRaises(TypeError, Root)
        self.assertRaises(TypeError, RootManager)
