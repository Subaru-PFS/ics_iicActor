import logging


class KeyRepo(object):
    def __init__(self, engine):
        self.engine = engine
        self.logger = logging.getLogger('KeyRepo')
        self.stateHolder = dict()  # just convenient.

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
        poweredOff.sort()
        return poweredOff

    def cacheHexapodState(self, cams):
        """Return cached hexapod state."""
        # Maybe not that robust but at least it's under my control.
        doCache = self.engine.visitManager.activeField.pfsDesign.designName == 'blackDots-moveAll'
        cached = False

        if doCache:
            current = self.getPoweredOffHexapods(cams)
            self.stateHolder['hexapodOff'] = current
            self.logger.info(f'caching powered off hexapod for {",".join(current)}')
        else:
            cached = self.stateHolder.pop('hexapodOff', False)
            self.logger.info(f'retrieving cached powered off hexapod for {",".join(cached)}')

        return cached

    def getActualArm(self, cam):
        """Get the actual arm being used for the given camera."""
        arm = cam.arm
        # checking current red resolution.
        if arm in 'rm':
            redResolution = self.getEnuKeyValue(cam.specName, 'rexm')
            arm = 'm' if redResolution == 'med' else 'r'

        return arm
