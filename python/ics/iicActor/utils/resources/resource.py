from ics.iicActor.utils import exception


class Resource(object):
    """Manage locking state for named resources with optional state tags."""

    default = 'nominal'

    @classmethod
    def getActor(cls, name: str) -> "Resource":
        """Return a Resource for an actor."""
        return cls(name)

    @classmethod
    def getPart(cls, name: str) -> "Resource":
        """Return a Resource for a part."""
        return cls(name)

    def __init__(self, name):
        """Initialize a resource with its name."""
        self.name = name
        self.available = True
        self.state = Resource.default

    def isAvailable(self, state):
        """Return True if resource is available or already in the requested state."""
        if state != Resource.default and self.state == state:
            return True

        return self.available

    def lock(self, state):
        """Lock the resource if available, or raise if already locked."""
        if not self.available:
            # Already locked — no conflict if same state
            if state != Resource.default and self.state == state:
                return

            raise exception.ResourceIsBusy(f'{self.name} already busy.')

        self.available = False
        self.state = state

    def free(self):
        """Free the resource and reset to default state."""
        self.available = True
        self.state = Resource.default

    @staticmethod
    def translate(resourceName):
        """Split resource name into (name, state), defaulting to nominal."""
        name, state = resourceName, Resource.default

        if '.' in resourceName:
            name, state = resourceName.split('.')

        return name, state
