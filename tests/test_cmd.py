import tests

from jurtlib.cmd import run, CommandError

class TestCmd(tests.Test):

    def test_run(self):
        output, status = run(["true"])
        self.assertEquals(output, "")
        self.assertEquals(status, 0)

    def test_error(self):
        output, status = run(["false"])
        self.assertEquals(output, "")
        self.assertEquals(status, 1)
        self.assertRaises(CommandError, run, ["false"], error=True)

    def test_stderr(self):
        args = ["python", "-c", r"import sys; sys.stderr.write('oops\n');"]
        output, status = run(args)
        self.assertEquals(output, "oops\n")
        self.assertEquals(status, 0)
