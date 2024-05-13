class KeyRepo(object):
    def __init__(self, engine):
        self.engine = engine

    @property
    def actor(self):
        return self.engine.actor

    def getEnuKeyValue(self, specName, keyName):
        """Return the value of the specified ENU key for the given spectrograph."""
        return self.actor.models[f'enu_{specName}'].keyVarDict[keyName].getValue()

    def getEnuKeyValues(self, cams, keyName):
        """Return a dictionary of ENU key values for the given cameras and key name."""
        specNames = list(set([cam.specName for cam in cams]))
        values = [self.getEnuKeyValue(specName, keyName) for specName in specNames]
        return dict([(specName, value) for specName, value in zip(specNames, values)])

    def getPoweredOffHexapods(self, cams):
        """Return a list of spectrograph names where the hexapod is powered off."""
        poweredOff = [specName for specName, (_, state, _, _, _) in self.getEnuKeyValues(cams, 'pduPort3').items() if
                      state == 'off']
        return poweredOff

    def getActualArm(self, cam):
        """Get the actual arm being used for the given camera."""
        arm = cam.arm
        # checking current red resolution.
        if arm in 'rm':
            redResolution = self.getEnuKeyValue(cam.specName, 'rexm')
            arm = 'm' if redResolution == 'med' else 'r'

        return arm
