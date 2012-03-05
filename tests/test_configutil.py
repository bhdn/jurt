import tests

from jurtlib import configutil

class TestConfigutil(tests.Test):

    def test_parsing_conf_fields(self):
        class DummyLogger:

            def __init__(self):
                self.calls = []

            def warn(self, fmt, *args):
                self.calls.append(fmt % args)
        configutil.logger = DummyLogger() # !!!!
        res = configutil.parse_conf_fields("", 1, "fieldname")
        self.assertEquals(res, [])
        res = configutil.parse_conf_fields("single", 1, "fieldname")
        self.assertEquals(res, [["single"]])
        res = configutil.parse_conf_fields("not single", 1, "fieldname")
        self.assertEquals(configutil.logger.calls,
                ["expected 1 fields in fieldname entry: not single"])
        self.assertEquals(res, [])
        res = configutil.parse_conf_fields("not single", 2, "fieldname")
        self.assertEquals(res, [["not", "single"]])

    def test_parsing_bool(self):
        self.assertEquals(True, configutil.parse_bool("yes"))
        self.assertEquals(False, configutil.parse_bool("no"))
        self.assertEquals(False, configutil.parse_bool(""))
        self.assertEquals(False, configutil.parse_bool("anythign else"))
