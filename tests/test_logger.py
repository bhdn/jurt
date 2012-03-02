import re
from os.path import join, exists, abspath

import tests

from jurtlib.config import JurtConfig
from jurtlib.logger import LoggerFactory, Logger, OutputLogger

class TestLoggerFactory(tests.Test):

    def test_create_logger_factory(self):
        config, targets = self.sample_config()
        target = targets[0][1]
        target.logs_dir = self.spooldir
        logid = "some-id"
        fac = LoggerFactory(target, config)
        logger = fac.get_logger(logid)
        self.assertTrue(exists(join(self.spooldir, logid)),
            "it did not create a logging work directory")
        for i in xrange(5):
            handler_name = "my-handler%d" % (i)
            handler = logger.get_output_handler(handler_name)
            expected_path = join(self.spooldir, logid, handler_name + ".log")
            self.assertTrue(exists(expected_path),
                "it did not create a log file for the output handler")
            self.assertEquals(abspath(handler.location()), expected_path,
                    "the path pointed by location is not the expected")
            handler.start()
            output_line = "something happened!\n"
            handler.write(output_line)
            handler.close()
            contents = open(expected_path).read()
            self.assertTrue(contents.startswith("==== started log at "))
            self.assertTrue(contents.splitlines()[-1].startswith(
                "==== closing log at "))
            self.assertTrue(output_line in contents)

    def test_output_handler_trap(self):
        config, targets = self.sample_config()
        target = targets[0][1]
        target.logs_dir = self.spooldir
        fac = LoggerFactory(target, config)
        test_re = re.compile("the value of foo is (?P<found>\w+)")
        logid = "some-id"
        logger = fac.get_logger(logid)
        handler = logger.get_output_handler("handler-name", trap=test_re)
        handler.start()
        handler.write("first line\n")
        handler.write("second line\n")
        handler.write("third line line\nthe value of foo is glarglarglar\n")
        handler.write("fourth line\n")
        handler.write("the value of foo is nhenhemnhenhem\nanother line\n")
        handler.write("sixth value\n")
        # matches between invocations of write() is not supported:
        handler.write("the value of ") 
        handler.write("foo is bugbugbug")
        handler.close()
        self.assertEquals(len(handler.matches), 2)
        self.assertEquals(handler.matches[0].group("found"), "glarglarglar")
        self.assertEquals(handler.matches[1].group("found"), "nhenhemnhenhem")
