import logging

from ics.utils.sps.exposureTiming import ExposureTiming


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
        self.deferredHexapodsOff = set()  # spectrograph names whose hexapod power-off is deferred.

    @property
    def actor(self):
        """Return the actor from the engine."""
        return self.engine.actor

    def getNirTiming(self, cams):
        """Return the H4 read time and IRP ratio shared by the NIR cameras in cams.

        Returned as the h4ReadTime and h4IrpRatio lamps keys, both None without NIR cameras.
        Raises RuntimeError if NIR cameras read with different timings (mixed IRP modes).
        """
        nirCams = [cam for cam in self.getSelectedCams(cams) if cam.startswith('n')]
        if not nirCams:
            return dict(h4ReadTime=None, h4IrpRatio=None)

        exposureTiming = ExposureTiming.fromInstdata()
        hxModels = [self.actor.models[f'hx_{cam}'] for cam in nirCams]
        timings = {(exposureTiming.readReadTime(hxModel), exposureTiming.readIrpRatio(hxModel)) for hxModel in hxModels}

        try:
            [(readTime, irpRatio)] = timings
        except ValueError:
            raise RuntimeError(f'Mixed IRP modes detected: NIR cameras have different (readTime, irpRatio) {timings}')

        return dict(h4ReadTime=readTime, h4IrpRatio=irpRatio)

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

    def deferHexapodsOff(self, specNames):
        """Record `specNames` as hexapods to power off by a later sequence."""
        self.deferredHexapodsOff.update(specNames)

        if specNames:
            self.logger.info(f'Deferring hexapod power-off for {", ".join(sorted(specNames))}')

    def popDeferredHexapodsOff(self, cams):
        """Remove and return the deferred hexapods among `cams` spectrographs, as a set of spectrograph names."""
        deferred = self.deferredHexapodsOff & {cam.specName for cam in cams}
        self.deferredHexapodsOff -= deferred

        if deferred:
            self.logger.info(f'Retrieving deferred hexapod power-off for {", ".join(sorted(deferred))}')

        return deferred

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
            The current red resolution ('low' or 'med').

        Raises
        ------
        RuntimeError
            If the current red resolution cannot be determined, or is neither 'low' nor 'med'.
        """
        try:
            [current] = set(self.getEnuKeyValues(cams, 'rexm').values())
        except ValueError:
            raise RuntimeError("Could not determine a unique current red resolution")

        if current not in ('low', 'med'):
            raise RuntimeError(f"Red resolution is {current}, not low or med")

        return current
