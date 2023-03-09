class KeyRepo(object):
    def __init__(self, engine):
        self.engine = engine

    @property
    def actor(self):
        return self.engine.actor

    def enuKeys(self, cams, keyName):
        """Get enu keys for that sequence given a key name."""
        specNames = list(set([cam.specName for cam in cams]))
        values = [self.actor.models[f'enu_{specName}'].keyVarDict[keyName].getValue() for specName in specNames]
        return dict([(specName, value) for specName, value in zip(specNames, values)])

    def hexapodPoweredOff(self, cams):
        """Return specName where the hexapod is powered off."""
        return [specName for specName, (_, state, _, _, _) in self.enuKeys(cams, 'pduPort3').items() if state == 'off']
