#!/usr/bin/python
import select
import sys
import subprocess

def main():
    cookie = None
    for i, arg in enumerate(sys.argv):
        if arg == "--cookie":
            cookie = sys.argv[i+1]
        elif arg == "--result":
            resultfile = sys.argv[i+1]
    if cookie:
        with open(resultfile, "w") as f:
            while True:
                rl, wl, xl = select.select([sys.stdin.fileno()], [],
                        [sys.stdin.fileno()])
                if rl:
                    line = sys.stdin.readline()
                    f.write("Argv: %s\n" %
                            subprocess.list2cmdline(sys.argv))
                    f.write("Line: %s\n" % line)
                    f.flush()
                    sys.stderr.write("\n%s OK\n" % (cookie))
                    sys.stderr.flush()
    else:
        with open(resultfile, "w") as f:
            f.write("Argv: %s\n" % subprocess.list2cmdline(sys.argv))

if __name__ == "__main__":
    main()
