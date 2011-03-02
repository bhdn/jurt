import os
import logging

logger = logging.getLogger("jurt.util")

def replace_link(linkpath, linkdest):
    if os.path.lexists(linkpath):
        if not os.path.islink(linkpath):
            newname = linkpath + "." + str(int(time.time()))
            logger.warn("%s already exists and it is not a symlink "
                    "as expected, renaming it to %s" % (linkpath,
                        newname))
            os.move(linkpath, newname)
        else:
            logger.debug("removing existing link %s" % (linkpath))
            os.unlink(linkpath)
    logger.debug("creating link %s pointing to %s" % (linkpath, linkdest))
    os.symlink(linkdest, linkpath)
