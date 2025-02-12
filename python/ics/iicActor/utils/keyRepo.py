import logging


class KeyRepo:
    """
    Repository to interactive Keyword dictionaries

    Parameters
    ----------
    engine : object
        The engine containing the actor and visit manager for state and command access.
    """

    def __init__(self, engine):
        self.engine = engine
        self.logger = logging.getLogger('KeyRepo')
        self.stateHolder = {}  # Cache for storing temporary states.

    @property
    def actor(self):
        """Return the actor from the engine."""
        return self.engine.actor

    def getEnuKeyValue(self, specName, keyName):
        """
        Retrieve the value of a specific ENU key for a given spectrograph.

        Parameters
        ----------
        specName : str
            Spectrograph name.
        keyName : str
            Key name to retrieve the value for.

        Returns
        -------
        Value of the specified ENU key.
        """
        return self.actor.models[f'enu_{specName}'].keyVarDict[keyName].getValue()

    def getEnuKeyValues(self, cams, keyName):
        """
        Retrieve ENU key values for a list of cameras and a specific key.

        Parameters
        ----------
        cams : list
            List of camera objects.
        keyName : str
            Key name to retrieve values for.

        Returns
        -------
        dict
            A dictionary with spectrograph names as keys and their ENU key values.
        """
        specNames = list(set([cam.specName for cam in cams]))
        values = [self.getEnuKeyValue(specName, keyName) for specName in specNames]
        return dict([(specName, value) for specName, value in zip(specNames, values)])

    def getPoweredOffHexapods(self, cams):
        """
        Get a list of spectrograph names where the hexapod is powered off.

        Parameters
        ----------
        cams : list
            List of camera objects.

        Returns
        -------
        list
            Sorted list of spectrograph names with hexapods powered off.
        """
        poweredOff = [
            specName for specName, (_, state, _, _, _)
            in self.getEnuKeyValues(cams, 'pduPort3').items()
            if state == 'off'
        ]
        poweredOff.sort()
        return poweredOff

    def cacheHexapodState(self, cams):
        """
        Cache or retrieve the hexapod power-off state based on the design name.

        Parameters
        ----------
        cams : list
            List of camera objects.

        Returns
        -------
        list or bool
            Cached hexapod state if caching is enabled, or `False` if not.
        """
        cached = []
        # Maybe not that robust but at least it's under my control
        doCache = self.engine.visitManager.activeField.pfsDesign.designName == 'blackDots-moveAll'
        current = self.getPoweredOffHexapods(cams)

        if doCache:
            self.stateHolder['hexapodOff'] = current
            self.logger.info(f'Caching powered-off hexapods for {", ".join(current)}')
        else:
            cached = self.stateHolder.pop('hexapodOff', [])
            self.logger.info(f'Retrieving cached powered-off hexapods for {", ".join(cached)}')

        return cached

    def getSelectedArms(self, cams):
        """
        Determine the unique set of arms selected for a list of cameras.

        Parameters
        ----------
        cams : list
            List of camera objects.

        Returns
        -------
        set
            Set of unique arms being used, adjusted according to red resolution if necessary.
        """
        return {cam[0] for cam in self.getSelectedCams(cams)}

    def getSelectedCams(self, cams):
        """
        Determine selected cams from the list of cameras, only matter for m-arm.

        Parameters
        ----------
        cams : list
            List of camera objects.

        Returns
        -------
        set
            Set of unique arms being used, adjusted according to red resolution if necessary.
        """

        def getSelectedCam(cam):
            """Determine the selected arm used for a given camera."""
            arm = cam.arm
            # Check if the arm is either 'r' or 'm' and adjust based on red resolution.
            if arm in {'r', 'm'}:
                redResolution = self.getEnuKeyValue(cam.specName, 'rexm')
                arm = 'm' if redResolution == 'med' else 'r'
            return f'{arm}{cam.specNum}'

        return [getSelectedCam(cam) for cam in cams]

    def getCurrentRedResolution(self, cams):
        """
        Determine the current red resolution setting for a list of cameras.

        Parameters
        ----------
        cams : list
            List of camera objects to check.

        Returns
        -------
        str
            The current red resolution ('med' or 'high').

        Raises
        ------
        RuntimeError
            If the current red resolution cannot be determined.
        """
        try:
            [current] = set(self.getEnuKeyValues(cams, 'rexm').values())
        except ValueError:
            raise RuntimeError("Could not determine a unique current red resolution")

        return current
