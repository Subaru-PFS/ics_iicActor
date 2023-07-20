import iicActor.utils.translate as translate
import numpy as np
from ics.iicActor.sps.sequence import SpsSequence
from ics.iicActor.sps.timedLamps import TimedLampsSequence
from ics.utils.sps.defocus import defocused_exposure_times_single_position


class Biases(SpsSequence):
    """ Biases sequence """
    seqtype = 'biases'
    lightBeam = False

    def __init__(self, cams, duplicate, **seqKeys):
        SpsSequence.__init__(self, cams, **seqKeys)

        self.expose('bias', 0, cams, duplicate=duplicate)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct MasterBiases object."""
        seqKeys = translate.seqKeys(cmdKeys)
        identKeys = translate.identKeys(cmdKeys)
        cams = iicActor.engine.resourceManager.spsConfig.identify(**identKeys)
        __, duplicate = translate.spsExposureKeys(cmdKeys, doRaise=False)

        return cls(cams, duplicate, **seqKeys)


class Darks(SpsSequence):
    """ Biases sequence """
    seqtype = 'darks'
    lightBeam = False

    def __init__(self, cams, exptime, duplicate, **seqKeys):
        SpsSequence.__init__(self, cams, **seqKeys)

        self.expose('dark', exptime, cams, duplicate=duplicate)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct MasterBiases object."""
        seqKeys = translate.seqKeys(cmdKeys)
        identKeys = translate.identKeys(cmdKeys)
        cams = iicActor.engine.resourceManager.spsConfig.identify(**identKeys)
        exptime, duplicate = translate.spsExposureKeys(cmdKeys, doRaise=False)

        return cls(cams, exptime, duplicate, **seqKeys)


class Arcs(TimedLampsSequence):
    """ Biases sequence """
    seqtype = 'arcs'

    def __init__(self, cams, lampsKeys, duplicate, **seqKeys):
        SpsSequence.__init__(self, cams, **seqKeys)

        self.expose('arc', lampsKeys, cams, duplicate=duplicate)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        seqKeys = translate.seqKeys(cmdKeys)
        identKeys = translate.identKeys(cmdKeys)
        __, duplicate = translate.spsExposureKeys(cmdKeys, doRaise=False)
        lampsKeys = translate.lampsKeys(cmdKeys)

        cams = iicActor.engine.resourceManager.spsConfig.identify(**identKeys)

        return cls(cams, lampsKeys, duplicate, **seqKeys)


class Flats(TimedLampsSequence):
    """ Biases sequence """
    seqtype = 'flats'

    def __init__(self, cams, lampsKeys, duplicate, windowKeys, **seqKeys):
        SpsSequence.__init__(self, cams, isWindowed=bool(windowKeys), **seqKeys)

        self.expose('flat', lampsKeys, cams, duplicate=duplicate, windowKeys=windowKeys)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        seqKeys = translate.seqKeys(cmdKeys)
        identKeys = translate.identKeys(cmdKeys)
        __, duplicate = translate.spsExposureKeys(cmdKeys, doRaise=False)
        windowKeys = translate.windowKeys(cmdKeys)
        lampsKeys = translate.lampsKeys(cmdKeys)

        cams = iicActor.engine.resourceManager.spsConfig.identify(**identKeys)

        return cls(cams, lampsKeys, duplicate, windowKeys, **seqKeys)


class Erase(SpsSequence):
    """ Sps erase. """
    seqtype = 'spsErase'

    def __init__(self, cams, duplicate, **seqKeys):
        SpsSequence.__init__(self, cams, **seqKeys)

        for i in range(duplicate):
            self.add('sps', 'erase', cams=cams)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        seqKeys = translate.seqKeys(cmdKeys)
        identKeys = translate.identKeys(cmdKeys)
        __, duplicate = translate.spsExposureKeys(cmdKeys, doRaise=False)

        cams = iicActor.engine.resourceManager.spsConfig.identify(**identKeys)

        return cls(cams, duplicate, **seqKeys)


class DitheredArcs(TimedLampsSequence):
    """ Dithered Arcs sequence """
    seqtype = 'ditheredArcs'

    def __init__(self, cams, lampsKeys, duplicate, pixelStep, hexapodOff, **seqKeys):
        SpsSequence.__init__(self, cams, **seqKeys)
        # start hexapod and move home.
        self.add('sps', 'slit start', cams=cams)
        self.add('sps', 'slit home', cams=cams)

        end = int(1 / pixelStep)
        start = 0
        for x in range(start, end):
            for y in range(start, end):
                xPix, yPix = x * pixelStep, y * pixelStep
                self.add('sps', 'slit dither', x=xPix, y=yPix, pixels=True, abs=True, cams=cams)
                self.expose('arc', lampsKeys, cams, duplicate=duplicate)

        # move back home and stop hexapod.
        self.add('sps', 'slit home', cams=cams)
        # Turn hexapod off only if it was off in the first place.
        if hexapodOff:
            self.add('sps', 'slit stop', specNums=','.join([specName[-1] for specName in hexapodOff]))

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        seqKeys = translate.seqKeys(cmdKeys)
        identKeys = translate.identKeys(cmdKeys)
        __, duplicate = translate.spsExposureKeys(cmdKeys, doRaise=False)
        lampsKeys = translate.lampsKeys(cmdKeys)
        pixelStep = cmdKeys['pixelStep'].values[0]

        cams = iicActor.engine.resourceManager.spsConfig.identify(**identKeys)
        hexapodOff = iicActor.engine.keyRepo.hexapodPoweredOff(cams)

        return cls(cams, lampsKeys, duplicate, pixelStep, hexapodOff, **seqKeys)


class DefocusedArcs(TimedLampsSequence):
    """ Defocus sequence """
    seqtype = 'defocusedArcs'

    def __init__(self, cams, lampsKeys, duplicate, positions, hexapodOff, **seqKeys):
        SpsSequence.__init__(self, cams, **seqKeys)
        # start hexapod and move home.
        self.add('sps', 'slit start', cams=cams)
        self.add('sps', 'slit home', cams=cams)

        for position in positions:
            multFactor, _ = defocused_exposure_times_single_position(exp_time_0=1, att_value_0=None,
                                                                     defocused_value=position)
            scaled = dict([(lamp, exptime * multFactor) for lamp, exptime in lampsKeys.items()])

            self.add('sps', 'slit', focus=position, abs=True, cams=cams)
            self.expose('arc', scaled, cams, duplicate=duplicate)

        # move back home and stop hexapod.
        self.add('sps', 'slit home', cams=cams)
        # Turn hexapod off only if it was off in the first place.
        if hexapodOff:
            self.add('sps', 'slit stop', specNums=','.join([specName[-1] for specName in hexapodOff]))

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        seqKeys = translate.seqKeys(cmdKeys)
        identKeys = translate.identKeys(cmdKeys)
        __, duplicate = translate.spsExposureKeys(cmdKeys, doRaise=False)
        lampsKeys = translate.lampsKeys(cmdKeys)
        start, stop, num = cmdKeys['position'].values
        positions = np.linspace(start, stop, num=int(num)).round(6)

        cams = iicActor.engine.resourceManager.spsConfig.identify(**identKeys)
        hexapodOff = iicActor.engine.keyRepo.hexapodPoweredOff(cams)

        return cls(cams, lampsKeys, duplicate, positions, hexapodOff, **seqKeys)


class FpaThroughFocus(TimedLampsSequence):
    """ FpaThroughFocus sequence. """
    seqtype = 'fpaThroughFocus'

    def __init__(self, cams, lampsKeys, duplicate, positions, **seqKeys):
        SpsSequence.__init__(self, cams, **seqKeys)

        for microns in positions:
            self.add('sps', 'fpa moveFocus', microns=microns, abs=True, cams=cams)
            self.expose('arc', lampsKeys, cams, duplicate=duplicate)

        # moving back to focus at the end.
        self.tail.add('sps', 'fpa toFocus', cams=cams)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        seqKeys = translate.seqKeys(cmdKeys)
        identKeys = translate.identKeys(cmdKeys)
        __, duplicate = translate.spsExposureKeys(cmdKeys, doRaise=False)
        lampsKeys = translate.lampsKeys(cmdKeys)
        start, stop, num = cmdKeys['micronsRange'].values
        positions = np.linspace(start, stop, num=int(num)).round(6)

        cams = iicActor.engine.resourceManager.spsConfig.identify(**identKeys)

        return cls(cams, lampsKeys, duplicate, positions, **seqKeys)
