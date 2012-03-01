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
        shutil.copytree(self.testrepoorig_dir, self.testrepo_dir)

    def tearDown(self):
        shutil.rmtree(self.spooldir)
