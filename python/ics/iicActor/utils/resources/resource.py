from iicActor.utils import exception


class Resource(object):
    default = 'nominal'

    @classmethod
    def getActor(cls, name: str) -> "Resource":
        return cls(name)

    @classmethod
    def getPart(cls, name: str) -> "Resource":
        return cls(name)

    def __init__(self, name):
        self.name = name
        self.available = True
        self.state = Resource.default

    def isAvailable(self, state):
        if state != Resource.default and self.state == state:
            return True

        return self.available

    def lock(self, state):
        """"""
        if not self.available:
            # no need to lock since it's already locked
            if state != Resource.default and self.state == state:
                return

            raise exception.ResourceIsBusy(f'{self.name} already busy.')

        self.available = False
        self.state = state

    def free(self):
        """"""
        self.available = True
        self.state = Resource.default

    @staticmethod
    def translate(resourceName):
        """Adding a special case for shutter closed basically."""
        name, state = resourceName, Resource.default

        if '.' in resourceName:
            name, state = resourceName.split('.')

        return name, state