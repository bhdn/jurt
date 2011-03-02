import os
import logging

logger = logging.getLogger("jurt.spool")

class Spool:

    def __init__(self, path, packagemanager):
        self.path = path
        self.packagemanager = packagemanager

    def create_dirs(self):
        if not os.path.exists(self.path):
            os.makedirs(self.path)
        self._update()

    def _update(self):
        self.packagemanager.update_repository_metadata(self.path)

    def package_count(self):
        return sum(1 for name in os.listdir(self.path)
                if self.packagemanager.valid_binary(name))

    def put_packages(self, paths):
        for path in paths:
            if self.packagemanager.valid_binary(path):
                dest = os.path.join(self.path, os.path.basename(path))
                logger.debug("creating hardlink from %s to %s" % (path, dest))
                os.link(path, dest)
            else:
                logger.debug("not copying %s to the spool at %s" % (path,
                    self.path))
        self._update()
