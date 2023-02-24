from ics.utils.sps.config import LightSource
from twisted.internet import reactor


class KeyBuffer(object):
    """Keyword buffer, through the callback *ONLY* when the value change."""

    def __init__(self, iicActor):
        super().__init__()
        self.iicActor = iicActor

        self.current = dict()
        self.future = dict()

    @property
    def lightSources(self):
        return [LightSource(self.current[f'sps.sm{specNum}LightSource']) for specNum in range(1, 5)]

    def attachCallback(self, actor, key, cb):
        """Attach a callback cb for a given actor,key pair, cb will be called only if the value changed."""

        def hasValueChanged(keyVar):
            """"""
            identifier = f'{actor}.{key}'

            try:
                vals = keyVar.getValue()
            except ValueError:
                vals = None

            # initialize if key is not present.
            if identifier not in self.current.keys():
                self.current[identifier] = vals
            # always update future dictionary.
            self.future[identifier] = vals
            # check for changes, delay is required because sometimes they are generated concurrently.
            reactor.callLater(1, self.checkForChanges, cb)

        self.iicActor.models[actor].keyVarDict[key].addCallback(hasValueChanged)

    def checkForChanges(self, cb):
        """Check if the keys has changed and call the callback if it is true."""
        if self.future != self.current:
            # if pfi is being disconnected then reset fpsDesignId.
            if 'pfi' in set(self.current.values()) - set(self.future.values()):
                self.iicActor.setFpsDesignId(None)

            self.current = self.future.copy()
            cb()
