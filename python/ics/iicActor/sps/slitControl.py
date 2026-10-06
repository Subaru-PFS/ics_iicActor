class SlitControl(object):
    """Which slit hexapods an sps sequence powers on, how it initialises them, and which it powers back off.

    Parameters
    ----------
    poweredOff : `list` of `str`
        Spectrograph names whose hexapod is powered off when the sequence is built.
    toStop : `list` of `str`
        Spectrograph names whose hexapod is powered off at the end of the sequence.
    fullInit : `bool`
        Start the powered-off hexapods with a home search rather than from the strut positions saved by slit stop.
    """
    # sps allows 120s per slit start, a home search from power-off takes ~90s.
    fullInitTimeLim = 150

    def __init__(self, poweredOff, toStop, fullInit):
        self.poweredOff = sorted(poweredOff)
        self.toStop = sorted(toStop)
        self.fullInit = fullInit

    @classmethod
    def fromConfig(cls, iicActor, cams, cmdKeys, seqtype, toStop=None):
        """Slit control of a sequence, from the iic slit config.

        The slit section of the `seqtype` config, if any, overrides the iic one, and a keepHexapodOn command keyword
        overrides both.

        Parameters
        ----------
        iicActor : `iicActor`
        cams : `list`
            Cameras of the sequence.
        cmdKeys : `opscore.protocols.keys.KeysDictionary`
        seqtype : `str`
        toStop : `list` of `str`, optional
            Spectrograph names to power off at the end, the powered-off ones by default.

        Returns
        -------
        `SlitControl`
        """
        config = dict(iicActor.actorConfig['slit'])
        config.update(iicActor.actorConfig.get(seqtype, {}).get('slit', {}))
        keepHexapodOn = config['keepHexapodOn'] or 'keepHexapodOn' in cmdKeys

        poweredOff = iicActor.engine.keyRepo.getPoweredOffHexapods(cams)
        toStop = poweredOff if toStop is None else toStop

        return cls(poweredOff, [] if keepHexapodOn else toStop, config['fullInit'])

    @staticmethod
    def selectCams(cams, specNames):
        """Cameras of `cams` belonging to one of `specNames`."""
        return [cam for cam in cams if cam.specName in specNames]

    @staticmethod
    def toSpecNums(specNames):
        """'sm1,sm3' style spectrograph names as a specNums argument, e.g. '1,3'."""
        return ','.join([specName[-1] for specName in specNames])

    def start(self, cmdList, cams):
        """Add the slit start commands for `cams` to `cmdList`.

        With fullInit, the powered-off hexapods are started first with a home search; the plain slit start that follows
        leaves an already started hexapod as it is.
        """
        if self.fullInit and self.poweredOff:
            cmdList.add('sps', 'slit start', fullInit=True, specNums=self.toSpecNums(self.poweredOff),
                        timeLim=SlitControl.fullInitTimeLim)

        cmdList.add('sps', 'slit start', cams=cams)

    def stop(self, cmdList):
        """Add the slit stop command of the hexapods to power off to `cmdList`, if any."""
        if self.toStop:
            cmdList.add('sps', 'slit stop', specNums=self.toSpecNums(self.toStop))
