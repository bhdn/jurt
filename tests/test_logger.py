import re
from os.path import join, exists, abspath
from cStringIO import StringIO

import tests

from jurtlib.config import JurtConfig
from jurtlib.logger import LoggerFactory, Logger, OutputLogger

class TestLoggerFactory(tests.Test):

    def _sample_logger(self, logid, outputfile=None):
        config, targets = self.sample_config()
        target = targets[0][1]
        target.logs_dir = self.spooldir
        fac = LoggerFactory(target, config)
        logger = fac.get_logger(logid, outputfile=outputfile)
        return logger

    def test_create_logger_factory(self):
        logid = "some-id"
        logger = self._sample_logger(logid)
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
            output_line = "something happened!\n"
            handler.write(output_line)
            handler.close()
            contents = open(expected_path).read()
            self.assertTrue(contents.startswith("==== started log at "))
            self.assertTrue(contents.splitlines()[-1].startswith(
                "==== closing log at "))
            self.assertTrue(output_line in contents)
        logger.done()

    def test_output_handler_trap(self):
        test_re = re.compile("the value of foo is (?P<found>\w+)")
        logid = "some-id"
        logger = self._sample_logger(logid)
        handler = logger.get_output_handler("handler-name", trap=test_re)
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
        logger.done()

    def test_outputfile(self):
        myfile = StringIO()
        logger = self._sample_logger("any log id, even with spaces",
                outputfile=myfile)
        handler = logger.get_output_handler("handler-name")
        handler.write("first line\n")
        handler.write("second line\nlast ")
        handler.write("line\n")
        handler.close()
        lines = myfile.getvalue().splitlines()
        self.assertTrue(lines[0].startswith("==== started log at "))
        self.assertEquals(lines[1], "first line")
        self.assertEquals(lines[2], "second line")
        self.assertEquals(lines[3], "last line")
        self.assertTrue(lines[4].startswith("==== closing log at "))

    def test_subpackage_and_logs(self):
        logid = "some-id"
        subpkg_name = "my-subpackage"
        nhandlers = 2
        logger = self._sample_logger(logid)
        names = ("pkg-a", "pkg-b", "pkg-c")
        for subpkg_name in names:
            subpkg = logger.subpackage(subpkg_name)
            for nhandler in xrange(nhandlers):
                handler_name = "handler-%d" % (nhandler)
                handler = subpkg.get_output_handler(handler_name)
                handler.write("foo bar baz\n")
                handler.write("that's it\n")
                handler.close()
        for subpkg_name in names:
            self.assertTrue(exists(join(self.spooldir, logid, subpkg_name,
                handler_name + ".log")))
        logs = logger.logs()
        self.assertEquals(2, len(logs))
        self.assertEquals(logs[0], logid)
        self.assertEquals(logs[1][0][0], "pkg-a")
        self.assertEquals(logs[1][0][1], abspath(join(self.spooldir, logid,
            "pkg-a", "handler-0.log")))
        self.assertEquals(logs[1][1][0], "pkg-a")
        self.assertEquals(logs[1][1][1], abspath(join(self.spooldir, logid,
            "pkg-a", "handler-1.log")))

        self.assertEquals(logs[1][2][0], "pkg-b")
        self.assertEquals(logs[1][2][1], abspath(join(self.spooldir, logid,
            "pkg-b", "handler-0.log")))
        self.assertEquals(logs[1][3][0], "pkg-b")
        self.assertEquals(logs[1][3][1], abspath(join(self.spooldir, logid,
            "pkg-b", "handler-1.log")))

        self.assertEquals(logs[1][4][0], "pkg-c")
        self.assertEquals(logs[1][4][1], abspath(join(self.spooldir, logid,
            "pkg-c", "handler-0.log")))
        self.assertEquals(logs[1][5][0], "pkg-c")
        self.assertEquals(logs[1][5][1], abspath(join(self.spooldir, logid,
            "pkg-c", "handler-1.log")))
