import ics.iicActor.utils.translate as translate
import numpy as np
from ics.iicActor.sps.sequence import SpsSequence
from ics.utils.sps.defocus import defocused_exposure_times_single_position


class DitheredFlats(SpsSequence):
    """ Dithered Flats sequence """
    seqtype = 'ditheredFlats'

    def __init__(self, cams, exptime, dcbOn, dcbOff, positions, duplicate, hexapodOff, **seqKeys):
        SpsSequence.__init__(self, cams, **seqKeys)

        # adding dcbOn and dcbOff commands.
        if any(dcbOn.values()):
            self.head.add('dcb', 'lamps', **dcbOn)

        if any(dcbOff.values()):
            self.tail.add('dcb', 'lamps', **dcbOff)

        # taking a trace before starting hexapod, (only for the one that were off in the first place).
        cameraWithHexapodPowerCycled = [cam for cam in cams if cam.specName in hexapodOff]
        if cameraWithHexapodPowerCycled:
            self.expose('flat', exptime, cameraWithHexapodPowerCycled, duplicate=duplicate)

        self.add('sps', 'slit start', cams=cams)

        # taking a trace in home to start.
        self.add('sps', 'slit home', cams=cams)
        self.expose('flat', exptime, cams, duplicate=duplicate)

        for position in positions:
            self.add('sps', 'slit dither', x=position, pixels=True, abs=True, cams=cams)
            self.expose('flat', exptime, cams, duplicate=duplicate)

        # taking a trace in home to end.
        self.add('sps', 'slit home', cams=cams)
        self.expose('flat', exptime, cams, duplicate=duplicate)

        # taking a trace after the hexapod is turned back off (only for the one that were off in the first place).
        if cameraWithHexapodPowerCycled:
            self.add('sps', 'slit stop', cams=cameraWithHexapodPowerCycled)
            self.expose('flat', exptime, cameraWithHexapodPowerCycled, duplicate=duplicate)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        cams = SpsSequence.keysToCam(iicActor, cmdKeys)
        seqKeys = translate.seqKeys(cmdKeys)
        exptime, duplicate = translate.spsExposureKeys(cmdKeys)
        dcbOn, dcbOff = translate.dcbKeys(cmdKeys, forceHalogen=True)
        positions = translate.ditheredFlatsKeys(cmdKeys)

        hexapodOff = iicActor.engine.keyRepo.getPoweredOffHexapods(cams)

        return cls(cams, exptime, dcbOn, dcbOff, positions, duplicate, hexapodOff, **seqKeys)


class FiberProfiles(SpsSequence):
    """ Dithered Flats sequence """
    seqtype = 'fiberProfiles'

    def __init__(self, cams, exptime, dcbOn, dcbOff, positions, duplicate, hexapodOff, interleaveDark, nTraceBefore,
                 nTraceAfter,
                 **seqKeys):
        SpsSequence.__init__(self, cams, **seqKeys)

        # adding dcbOn and dcbOff commands.
        if any(dcbOn.values()):
            self.head.add('dcb', 'lamps', **dcbOn)

        if any(dcbOff.values()):
            self.tail.add('dcb', 'lamps', **dcbOff)

        # taking a trace in home to start.
        self.add('sps', 'slit start', cams=cams)
        self.add('sps', 'slit home', cams=cams)
        # taking nTraceBefore images in home first.
        self.takeOneDuplicate(exptime, cams, int(duplicate * nTraceBefore), interleaveDark)

        for position in positions:
            self.add('sps', 'slit dither', x=position, pixels=True, abs=True, cams=cams)
            self.takeOneDuplicate(exptime, cams, duplicate, interleaveDark)

        # taking a trace in home to end.
        self.add('sps', 'slit home', cams=cams)
        self.takeOneDuplicate(exptime, cams, int(duplicate * nTraceAfter), interleaveDark)

        # Turn hexapod off only if it was off in the first place.
        if hexapodOff:
            self.add('sps', 'slit stop', specNums=','.join([specName[-1] for specName in hexapodOff]))

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys, hexapodOff=False):
        """Defining rules to construct ScienceObject object."""
        cams = SpsSequence.keysToCam(iicActor, cmdKeys)
        seqKeys = translate.seqKeys(cmdKeys)
        exptime, duplicate = translate.spsExposureKeys(cmdKeys)
        dcbOn, dcbOff = translate.dcbKeys(cmdKeys, forceHalogen=True)
        positions = translate.fiberProfilesKeys(cmdKeys)
        interleaveDark = cmdKeys['interleaveDark'].values[0] if 'interleaveDark' in cmdKeys else False

        actorConfig = iicActor.actorConfig['fiberProfiles']
        nTraceBefore = cmdKeys['nTraceBefore'].values[0] if 'nTraceBefore' in cmdKeys else actorConfig['nTraceBefore']
        nTraceAfter = cmdKeys['nTraceAfter'].values[0] if 'nTraceAfter' in cmdKeys else actorConfig['nTraceAfter']

        return cls(cams, exptime, dcbOn, dcbOff, positions, duplicate, hexapodOff, interleaveDark, nTraceBefore,
                   nTraceAfter,
                   **seqKeys)

    def takeOneDuplicate(self, exptime, cams, duplicate, interleaveDark):
        """take one duplicate, interleave for nir arm if necessary."""
        nirCam = [cam for cam in cams if cam.arm == 'n']

        for i in range(duplicate):
            self.expose('flat', exptime, cams, duplicate=1)
            # interleave dark for nir.
            if nirCam and interleaveDark:
                SpsSequence.expose(self, 'dark', interleaveDark, nirCam, duplicate=1)

    def setComments(self, rdaPosition):
        """Setting default comments."""
        self.comments = 'brn arm' if rdaPosition == 'low' else 'bmn arm'


class Arcs(SpsSequence):
    """ Biases sequence """
    seqtype = 'arcs'

    def __init__(self, cams, exptime, dcbOn, dcbOff, duplicate, **seqKeys):
        SpsSequence.__init__(self, cams, **seqKeys)

        # adding dcbOn and dcbOff commands.
        if any(dcbOn.values()):
            self.head.add('dcb', 'lamps', **dcbOn)

        if any(dcbOff.values()):
            self.tail.add('dcb', 'lamps', **dcbOff)

        self.expose('arc', exptime, cams, duplicate=duplicate)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        cams = SpsSequence.keysToCam(iicActor, cmdKeys)
        seqKeys = translate.seqKeys(cmdKeys)
        exptime, duplicate = translate.spsExposureKeys(cmdKeys)
        dcbOn, dcbOff = translate.dcbKeys(cmdKeys)

        return cls(cams, exptime, dcbOn, dcbOff, duplicate, **seqKeys)


class Flats(SpsSequence):
    """ Biases sequence """
    seqtype = 'flats'

    def __init__(self, cams, exptime, dcbOn, dcbOff, duplicate, windowKeys, **seqKeys):
        SpsSequence.__init__(self, cams, isWindowed=bool(windowKeys), **seqKeys)

        # adding dcbOn and dcbOff commands.
        if any(dcbOn.values()):
            self.head.add('dcb', 'lamps', **dcbOn)

        if any(dcbOff.values()):
            self.tail.add('dcb', 'lamps', **dcbOff)

        self.expose('flat', exptime, cams, duplicate=duplicate, windowKeys=windowKeys)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        cams = SpsSequence.keysToCam(iicActor, cmdKeys)
        seqKeys = translate.seqKeys(cmdKeys)
        exptime, duplicate = translate.spsExposureKeys(cmdKeys)
        windowKeys = translate.windowKeys(cmdKeys)
        dcbOn, dcbOff = translate.dcbKeys(cmdKeys, forceHalogen=True)

        return cls(cams, exptime, dcbOn, dcbOff, duplicate, windowKeys, **seqKeys)


class ScienceArc(Arcs):
    """ Biases sequence """
    seqtype = 'scienceArc'
    doScienceCheck = True


class ScienceTrace(Flats):
    """ Biases sequence """
    seqtype = 'scienceTrace'
    doScienceCheck = True


class DitheredArcs(SpsSequence):
    """ Dithered Arcs sequence """
    seqtype = 'ditheredArcs'

    def __init__(self, cams, exptime, dcbOn, dcbOff, duplicate, pixelStep, hexapodOff, **seqKeys):
        SpsSequence.__init__(self, cams, **seqKeys)

        # adding dcbOn and dcbOff commands.
        if any(dcbOn.values()):
            self.head.add('dcb', 'lamps', **dcbOn)

        if any(dcbOff.values()):
            self.tail.add('dcb', 'lamps', **dcbOff)

        # start hexapod and move home.
        self.add('sps', 'slit start', cams=cams)
        self.add('sps', 'slit home', cams=cams)

        end = int(1 / pixelStep)
        start = 0
        for x in range(start, end):
            for y in range(start, end):
                xPix, yPix = x * pixelStep, y * pixelStep
                self.add('sps', 'slit dither', x=xPix, y=yPix, pixels=True, abs=True, cams=cams)
                self.expose('arc', exptime, cams, duplicate=duplicate)

        # move back home and stop hexapod.
        self.add('sps', 'slit home', cams=cams)
        # Turn hexapod off only if it was off in the first place.
        if hexapodOff:
            self.add('sps', 'slit stop', specNums=','.join([specName[-1] for specName in hexapodOff]))

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        seqKeys = translate.seqKeys(cmdKeys)
        cams = SpsSequence.keysToCam(iicActor, cmdKeys)
        exptime, duplicate = translate.spsExposureKeys(cmdKeys)
        dcbOn, dcbOff = translate.dcbKeys(cmdKeys)
        pixelStep = cmdKeys['pixelStep'].values[0]
        hexapodOff = iicActor.engine.keyRepo.getPoweredOffHexapods(cams)

        return cls(cams, exptime, dcbOn, dcbOff, duplicate, pixelStep, hexapodOff, **seqKeys)


class DetThroughFocus(SpsSequence):
    """ Detector through focus sequence """
    seqtype = 'detThroughFocus'

    def __init__(self, cams, exptime, dcbOn, dcbOff, duplicate, positions, **seqKeys):
        SpsSequence.__init__(self, cams, **seqKeys)

        # adding dcbOn and dcbOff commands.
        if any(dcbOn.values()):
            self.head.add('dcb', 'lamps', **dcbOn)

        if any(dcbOff.values()):
            self.tail.add('dcb', 'lamps', **dcbOff)

        for motorA, motorB, motorC in positions:
            self.add('sps', 'ccdMotors move', a=motorA, b=motorB, c=motorC, microns=True, abs=True, cams=cams)
            self.expose('arc', exptime, cams, duplicate=duplicate)

        # moving back to focus at the end.
        self.tail.add('sps', 'fpa toFocus', cams=cams)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        seqKeys = translate.seqKeys(cmdKeys)
        cams = SpsSequence.keysToCam(iicActor, cmdKeys)
        exptime, duplicate = translate.spsExposureKeys(cmdKeys)
        dcbOn, dcbOff = translate.dcbKeys(cmdKeys)
        # translating from given position and tilt.
        positions = translate.detThroughFocusKeys(cmdKeys)

        return cls(cams, exptime, dcbOn, dcbOff, duplicate, positions, **seqKeys)


class FpaThroughFocus(SpsSequence):
    """ FpaThroughFocus sequence. """
    seqtype = 'fpaThroughFocus'

    def __init__(self, cams, exptime, dcbOn, dcbOff, duplicate, positions, **seqKeys):
        SpsSequence.__init__(self, cams, **seqKeys)

        # adding dcbOn and dcbOff commands.
        if any(dcbOn.values()):
            self.head.add('dcb', 'lamps', **dcbOn)

        if any(dcbOff.values()):
            self.tail.add('dcb', 'lamps', **dcbOff)

        for microns in positions:
            # we do a relative move to focus position.
            self.add('sps', 'fpa moveFocus', microns=microns, abs=False, cams=cams)
            self.expose('arc', exptime, cams, duplicate=duplicate)

        # moving back to focus at the end.
        self.tail.add('sps', 'fpa toFocus', cams=cams)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        cams = SpsSequence.keysToCam(iicActor, cmdKeys)
        seqKeys = translate.seqKeys(cmdKeys)
        exptime, duplicate = translate.spsExposureKeys(cmdKeys)
        dcbOn, dcbOff = translate.dcbKeys(cmdKeys)
        start, stop, num = cmdKeys['micronsRange'].values
        positions = np.linspace(start, stop, num=int(num)).round(6)

        return cls(cams, exptime, dcbOn, dcbOff, duplicate, positions, **seqKeys)


class SlitThroughFocus(SpsSequence):
    """Slit through focus sequence."""
    seqtype = 'slitThroughFocus'

    def __init__(self, cams, exptime, dcbOn, dcbOff, duplicate, positions, **seqKeys):
        SpsSequence.__init__(self, cams, **seqKeys)

        # adding dcbOn and dcbOff commands.
        if any(dcbOn.values()):
            self.head.add('dcb', 'lamps', **dcbOn)

        if any(dcbOff.values()):
            self.tail.add('dcb', 'lamps', **dcbOff)

        for focus in positions:
            self.add('sps', 'slit', focus=focus, abs=True, cams=cams)
            self.expose('arc', exptime, cams, duplicate=duplicate)

        # moving back to focus at the end.
        self.tail.add('sps', 'slit', focus=0, abs=True, cams=cams)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        seqKeys = translate.seqKeys(cmdKeys)
        cams = SpsSequence.keysToCam(iicActor, cmdKeys)
        exptime, duplicate = translate.spsExposureKeys(cmdKeys)
        dcbOn, dcbOff = translate.dcbKeys(cmdKeys)
        # translating from given position and tilt.
        positions = translate.slitThroughFocusKeys(cmdKeys)

        return cls(cams, exptime, dcbOn, dcbOff, duplicate, positions, **seqKeys)


class DefocusedArcs(SpsSequence):
    """ Defocus sequence """
    seqtype = 'defocusedArcs'

    def __init__(self, cams, exptime, dcbOn, dcbOff, duplicate, positions, hexapodOff, **seqKeys):
        SpsSequence.__init__(self, cams, **seqKeys)

        # adding dcbOn and dcbOff commands.
        if any(dcbOn.values()):
            self.head.add('dcb', 'lamps', **dcbOn)

        if any(dcbOff.values()):
            self.tail.add('dcb', 'lamps', **dcbOff)

        # start hexapod and move home.
        self.add('sps', 'slit start', cams=cams)
        self.add('sps', 'slit home', cams=cams)

        for position in positions:
            multFactor, _ = defocused_exposure_times_single_position(exp_time_0=1, att_value_0=None,
                                                                     defocused_value=position)
            scaled = [expTime * multFactor for expTime in exptime]

            self.add('sps', 'slit', focus=position, abs=True, cams=cams)
            self.expose('arc', scaled, cams, duplicate=duplicate)

        # move back home.
        self.add('sps', 'slit home', cams=cams)
        # Turn hexapod off only if it was off in the first place.
        if hexapodOff:
            self.add('sps', 'slit stop', specNums=','.join([specName[-1] for specName in hexapodOff]))

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        seqKeys = translate.seqKeys(cmdKeys)
        cams = SpsSequence.keysToCam(iicActor, cmdKeys)
        exptime, duplicate = translate.spsExposureKeys(cmdKeys)
        dcbOn, dcbOff = translate.dcbKeys(cmdKeys)
        # basic np.linspace.
        start, stop, num = cmdKeys['position'].values
        positions = np.linspace(start, stop, num=int(num)).round(6)
        hexapodOff = iicActor.engine.keyRepo.getPoweredOffHexapods(cams)

        return cls(cams, exptime, dcbOn, dcbOff, duplicate, positions, hexapodOff, **seqKeys)
