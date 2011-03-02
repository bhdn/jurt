
class Registry:
    register = dict.__setitem__

    def __init__(self):
        self._classes = {}

    def register(self, name, class_):
        self._classes[name] = class_

    def get_instance(self, name, *args, **kwargs):
        class_ = self.get_class(name)
        instance = class_(*args, **kwargs)
        return instance

    def get_class(self, name):
        class_ = self._classes[name]
        return class_
