import logging
log = logging.getLogger("jurt")

class Error(Exception):
    pass

class CommandError(Error):

    def __init__(self, returncode, cmdline, output):
        self.returncode = returncode
        self.cmdline = cmdline
        self.output = output
        msg = ("command failed with exit code "
                "%d\n%s\n%s" % (returncode, cmdline, output))
        self.args = (msg,)


class SetupError(Error):
    """Jurt not properly installed not the system"""
