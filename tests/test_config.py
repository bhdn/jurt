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
"""
        config = self.config_class()
        config.parse(contents)
        self.assertEquals(config.first.foo, "bar")
        self.assertEquals(config.first.bar, "baz")
        self.assertEquals(config.second_section.foo, ("multi-\nline "
            "configuration\noption"))
        self.assertEquals(config.second_section.it_sucks_but, "it")

class TestJurtConfig(TestConfig):

    config_class = JurtConfig

    def test_parsed_defaults(self):
        config = self.config_class()
        self.assertIsInstance(config.jurt, SectionWrapper)
        self.assertIsInstance(config.root, SectionWrapper)
        self.assertTrue("any target" in config.config_object().sections(), 
                "no section 'any target' defined")
