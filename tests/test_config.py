import tests

from jurtlib.config import Config, JurtConfig, SectionWrapper

class TestConfig(tests.Test):

    config_class = Config

    def test_create_config(self):
        config = self.config_class()

    def test_parse_and_config_mapping(self):
        contents = """\
[first]
foo = bar
bar = baz

[second-section]
foo = multi-
  line configuration 
  option
it-sucks-but = it ; ignores semicolons
empty = 
"""
        config = self.config_class()
        config.parse(contents)
        self.assertEquals(config.first.foo, "bar")
        self.assertEquals(config.first.bar, "baz")
        self.assertEquals(config.second_section.foo, ("multi-\nline "
            "configuration\noption"))
        self.assertEquals(config.second_section.it_sucks_but, "it")
        self.assertEquals(config.second_section.empty, "")

class TestJurtConfig(TestConfig):

    config_class = JurtConfig

    def test_parsed_defaults(self):
        config = self.config_class()
        self.assertIsInstance(config.jurt, SectionWrapper)
        self.assertIsInstance(config.root, SectionWrapper)
        self.assertTrue("any target" in config.config_object().sections(), 
                "no section 'any target' defined")

    def test_target_conf(self):
        contents = """\
[any target]
foo = any-bar
zlarg = klakla

[target first]
foo = bar
bar = baz

[target second]
foo = second-bar
bar = second-baz
"""
        config = self.config_class()
        config.parse(contents)
        targets = list(config.targets())
        self.assertEquals(targets[0][1].target_name, "first")
        self.assertEquals(targets[0][1].foo, "bar")
        self.assertEquals(targets[0][1].bar, "baz")
        self.assertEquals(targets[0][1].zlarg, "klakla")
        self.assertEquals(targets[1][1].target_name, "second")
        self.assertEquals(targets[1][1].foo, "second-bar")
        self.assertEquals(targets[1][1].bar, "second-baz")
        self.assertEquals(targets[1][1].zlarg, "klakla")
