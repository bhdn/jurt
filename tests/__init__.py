import os
from unittest import TestCase
from os.path import join
import shutil

class Test(TestCase):
    
    def setUp(self):
        self.rootdir = join(os.getcwd(), "tests")
        self.sharedir = join(self.rootdir, "data/")
        self.spooldir = join(self.rootdir, "spool/")
        #

        os.makedirs(self.spooldir)
        #shutil.copytree(self.testrepoorig_dir, self.testrepo_dir)

    def tearDown(self):
        shutil.rmtree(self.spooldir)

    def sample_config(self):
        from jurtlib.config import JurtConfig
        contents = """\
[target first]
foo = bar
bar = baz

[target second]
foo = second-bar
bar = second-baz
"""
        config = JurtConfig()
        config.parse(contents)
        return config, tuple(config.targets())
