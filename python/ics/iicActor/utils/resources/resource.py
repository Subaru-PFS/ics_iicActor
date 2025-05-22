from iicActor.utils import exception


class Resource(object):
    default = 'nominal'

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

    def translate(self):
        """Adding a special case for shutter closed basically."""
        state = Resource.default
        # special case when required shutters closed
        if '.closed' in required:
            resourceName, state = required.split('.')
        if '.off' in required:
            resourceName, state = required.split('.')

        return resourceName, state

    def free(self):
        """"""
        self.available = True
        self.state = Resource.default
