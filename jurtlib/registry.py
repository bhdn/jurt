from jurtlib import Error

class Registry:
    register = dict.__setitem__

    def __init__(self, description):
        self._classes = {}
        self.description = description

    def register(self, name, class_):
        self._classes[name] = class_

    def get_instance(self, name, *args, **kwargs):
        class_ = self.get_class(name)
        instance = class_(*args, **kwargs)
        return instance

    def get_class(self, name):
        try:
            class_ = self._classes[name]
        except KeyError:
            raise Error, "no such %s: %s" % (self.description, name)
        return class_
