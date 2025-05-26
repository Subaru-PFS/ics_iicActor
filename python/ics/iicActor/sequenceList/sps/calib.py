import iicActor.utils.translate as translate
from ics.iicActor.sps.sequence import SpsSequence
from ics.iicActor.sps.timedLamps import TimedLampsSequence
from iicActor.sequenceList.sps.base import Biases, Darks, Arcs, Flats


class MasterBiases(Biases):
    """ MasterBiases sequence """
    seqtype = 'masterBiases'
    minDuplicate = 15

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct MasterBiases object."""
        cams = SpsSequence.keysToCam(iicActor, cmdKeys)
        seqKeys = translate.seqKeys(cmdKeys)
        __, duplicate = translate.spsExposureKeys(cmdKeys, doRaise=False, defaultDuplicate=25)

        if duplicate < MasterBiases.minDuplicate:
            raise RuntimeError(f'masterBiases should at least contains {MasterBiases.minDuplicate} duplicates !')

        if iicActor.scrLightsOn:
            raise RuntimeError(f'SCR lights should be off for masterBiases !')

        seqKeys['name'] = 'calibProduct' if not seqKeys['name'] else seqKeys['name']

        return cls(cams, duplicate, **seqKeys)


class MasterDarks(Darks):
    """ MasterDarks sequence """
    seqtype = 'masterDarks'
    minDuplicate = 15

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct MasterDarks object."""
        cams = SpsSequence.keysToCam(iicActor, cmdKeys)
        seqKeys = translate.seqKeys(cmdKeys)
        exptime, duplicate = translate.spsExposureKeys(cmdKeys, doRaise=False, defaultDuplicate=25)

        if duplicate < MasterBiases.minDuplicate:
            raise RuntimeError(f'masterDarks should at least contains {MasterDarks.minDuplicate} duplicates !')

        if iicActor.scrLightsOn:
            raise RuntimeError(f'SCR lights should be off for masterDarks !')

        seqKeys['name'] = 'calibProduct' if not seqKeys['name'] else seqKeys['name']

        return cls(cams, exptime, duplicate, **seqKeys)


class DitheredFlats(TimedLampsSequence):
    """ Dithered Flats sequence """
    seqtype = 'ditheredFlats'

    def __init__(self, cams, lampsKeys, positions, duplicate, hexapodOff, interleaveDark, **seqKeys):
        SpsSequence.__init__(self, cams, **seqKeys)

        # taking a trace before starting hexapod, (for the one that were off in the first place).
        cameraWithHexapodPowerCycled = [cam for cam in cams if cam.specName in hexapodOff]
        if cameraWithHexapodPowerCycled:
            self.takeOneDuplicate(lampsKeys, cameraWithHexapodPowerCycled, duplicate, interleaveDark)

        # taking a trace in home to start.
        self.add('sps', 'slit start', cams=cams)
        self.add('sps', 'slit home', cams=cams)
        self.takeOneDuplicate(lampsKeys, cams, duplicate, interleaveDark)

        for position in positions:
            self.add('sps', 'slit dither', x=position, pixels=True, abs=True, cams=cams)
            self.takeOneDuplicate(lampsKeys, cams, duplicate, interleaveDark)

        # taking a trace in home to end.
        self.add('sps', 'slit home', cams=cams)
        self.takeOneDuplicate(lampsKeys, cams, duplicate, interleaveDark)

        # taking a trace after the hexapod is turned back off (for the one that were off in the first place).
        if cameraWithHexapodPowerCycled:
            self.add('sps', 'slit stop', cams=cameraWithHexapodPowerCycled)
            self.takeOneDuplicate(lampsKeys, cameraWithHexapodPowerCycled, duplicate, interleaveDark)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        cams = SpsSequence.keysToCam(iicActor, cmdKeys)
        seqKeys = translate.seqKeys(cmdKeys)
        __, duplicate = translate.spsExposureKeys(cmdKeys, doRaise=False)
        lampsKeys = translate.lampsKeys(cmdKeys)
        positions = translate.ditheredFlatsKeys(cmdKeys)

        hexapodOff = iicActor.engine.keyRepo.getPoweredOffHexapods(cams)
        interleaveDark = cmdKeys['interleaveDark'].values[0] if 'interleaveDark' in cmdKeys else False

        return cls(cams, lampsKeys, positions, duplicate, hexapodOff, interleaveDark, **seqKeys)

    def takeOneDuplicate(self, lampsKeys, cams, duplicate, interleaveDark):
        """take one duplicate, interleave for nir arm if necessary."""
        nirCam = [cam for cam in cams if cam.arm == 'n']

        for i in range(duplicate):
            self.expose('flat', lampsKeys, cams, duplicate=1)
            # interleave dark for nir.
            if nirCam and interleaveDark:
                SpsSequence.expose(self, 'dark', interleaveDark, nirCam, duplicate=1)


class FiberProfiles(TimedLampsSequence):
    """ Dithered Flats sequence """
    seqtype = 'fiberProfiles'

    def __init__(self, cams, lampsKeys, positions, duplicate, hexapodOff, interleaveDark, nTraceBefore, nTraceAfter,
                 **seqKeys):
        SpsSequence.__init__(self, cams, **seqKeys)

        # taking a trace in home to start.
        self.add('sps', 'slit start', cams=cams)
        self.add('sps', 'slit home', cams=cams)
        # taking nTraceBefore images in home first.
        self.takeOneDuplicate(lampsKeys, cams, int(duplicate * nTraceBefore), interleaveDark)

        for position in positions:
            self.add('sps', 'slit dither', x=position, pixels=True, abs=True, cams=cams)
            self.takeOneDuplicate(lampsKeys, cams, duplicate, interleaveDark)

        # taking a trace in home to end.
        self.add('sps', 'slit home', cams=cams)
        self.takeOneDuplicate(lampsKeys, cams, int(duplicate * nTraceAfter), interleaveDark)

        # Turn hexapod off only if it was off in the first place.
        if hexapodOff:
            self.add('sps', 'slit stop', specNums=','.join([specName[-1] for specName in hexapodOff]))

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys, hexapodOff=False):
        """Defining rules to construct ScienceObject object."""
        cams = SpsSequence.keysToCam(iicActor, cmdKeys)
        seqKeys = translate.seqKeys(cmdKeys)
        __, duplicate = translate.spsExposureKeys(cmdKeys, doRaise=False)
        lampsKeys = translate.lampsKeys(cmdKeys)
        positions = translate.fiberProfilesKeys(cmdKeys)
        interleaveDark = cmdKeys['interleaveDark'].values[0] if 'interleaveDark' in cmdKeys else False

        actorConfig = iicActor.actorConfig['fiberProfiles']
        nTraceBefore = cmdKeys['nTraceBefore'].values[0] if 'nTraceBefore' in cmdKeys else actorConfig['nTraceBefore']
        nTraceAfter = cmdKeys['nTraceAfter'].values[0] if 'nTraceAfter' in cmdKeys else actorConfig['nTraceAfter']

        return cls(cams, lampsKeys, positions, duplicate, hexapodOff, interleaveDark, nTraceBefore, nTraceAfter,
                   **seqKeys)

    def takeOneDuplicate(self, lampsKeys, cams, duplicate, interleaveDark):
        """take one duplicate, interleave for nir arm if necessary."""
        nirCam = [cam for cam in cams if cam.arm == 'n']

        for i in range(duplicate):
            self.expose('flat', lampsKeys, cams, duplicate=1)
            # interleave dark for nir.
            if nirCam and interleaveDark:
                SpsSequence.expose(self, 'dark', interleaveDark, nirCam, duplicate=1)

    def setComments(self, rdaPosition):
        """Setting default comments."""
        self.comments = 'brn arm' if rdaPosition == 'low' else 'bmn arm'


class ShutterDriftFlats(SpsSequence):
    """ Dithered Flats sequence """
    seqtype = 'driftFlats'

    def __init__(self, cams, exptime, duplicate, pixMin, pixMax, doStopHexapod, **seqKeys):
        SpsSequence.__init__(self, cams, **seqKeys)

        # go home first.
        self.add('sps', 'slit start', cams=cams)

        for iDuplicate in range(duplicate):
            # moving to the beginning of the range // required for N.
            self.add('sps', 'slit dither', x=pixMin, pixels=True, abs=True, cams=cams)
            self.expose('flat', exptime, cams, duplicate=1, slideSlit=f'{pixMin:.1f},{pixMax:.1f}')

        # move back home
        self.tail.add('sps', 'slit home', cams=cams)
        # stop hexapod if required.
        if doStopHexapod:
            self.tail.add('sps', 'slit stop', cams=cams)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        cams = SpsSequence.keysToCam(iicActor, cmdKeys)
        seqKeys = translate.seqKeys(cmdKeys)
        exptime, duplicate = translate.spsExposureKeys(cmdKeys)

        pixMin, pixMax, num = cmdKeys['pixelRange'].values
        doStopHexapod = 'keepHexapodOn' not in cmdKeys

        return cls(cams, exptime, duplicate, pixMin, pixMax, doStopHexapod, **seqKeys)


class DriftFlats(ShutterDriftFlats, TimedLampsSequence):
    """ Dithered Flats sequence """

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        cams = SpsSequence.keysToCam(iicActor, cmdKeys)
        seqKeys = translate.seqKeys(cmdKeys)
        __, duplicate = translate.spsExposureKeys(cmdKeys, doRaise=False)
        lampsKeys = translate.lampsKeys(cmdKeys)
        pixMin, pixMax, num = cmdKeys['pixelRange'].values
        doStopHexapod = 'keepHexapodOn' not in cmdKeys

        return cls(cams, lampsKeys, duplicate, pixMin, pixMax, doStopHexapod, **seqKeys)


class ScienceArc(Arcs):
    """ Biases sequence """
    seqtype = 'scienceArc'
    doScienceCheck = True


class ScienceTrace(Flats):
    """ Biases sequence """
    seqtype = 'scienceTrace'
    doScienceCheck = True


class DomeFlat(SpsSequence):
    """ Biases sequence """
    seqtype = 'domeFlat'
    doScienceCheck = True

    def __init__(self, cams, exptime, duplicate, windowKeys, **seqKeys):
        SpsSequence.__init__(self, cams, isWindowed=bool(windowKeys), **seqKeys)

        self.expose('domeflat', exptime, cams, duplicate=duplicate, windowKeys=windowKeys)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        cams = SpsSequence.keysToCam(iicActor, cmdKeys)
        seqKeys = translate.seqKeys(cmdKeys)
        exptime, duplicate = translate.spsExposureKeys(cmdKeys)
        windowKeys = translate.windowKeys(cmdKeys)

        return cls(cams, exptime, duplicate, windowKeys, **seqKeys)
