import subprocess
from jurtlib import Error

class CommandError(Error):
    pass

def run(args, error=False):
    proc = subprocess.Popen(args=args, shell=False,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    proc.wait()
    output = proc.stdout.read()
    if proc.returncode != 0 and error:
        cmdline = subprocess.list2cmdline(cmd)
        raise CommandError, ("command failed: %s\n%s\n" %
                (cmdline, output))
    return output, proc.returncode
