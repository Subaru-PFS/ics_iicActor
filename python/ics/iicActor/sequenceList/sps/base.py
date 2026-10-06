import ics.iicActor.utils.translate as translate
import numpy as np
from ics.iicActor.sps.sequence import SpsSequence
from ics.iicActor.sps.slitControl import SlitControl
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
        cams = SpsSequence.keysToCam(iicActor, cmdKeys)
        seqKeys = translate.seqKeys(cmdKeys)
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
        cams = SpsSequence.keysToCam(iicActor, cmdKeys)
        seqKeys = translate.seqKeys(cmdKeys)
        exptime, duplicate = translate.spsExposureKeys(cmdKeys, doRaise=False)

        return cls(cams, exptime, duplicate, **seqKeys)


class Arcs(TimedLampsSequence):
    """ Biases sequence """
    seqtype = 'arcs'
    exptype = 'arc'

    def __init__(self, cams, lampsKeys, duplicate, **seqKeys):
        SpsSequence.__init__(self, cams, **seqKeys)

        self.expose(self.exptype, lampsKeys, cams, duplicate=duplicate)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        cams = SpsSequence.keysToCam(iicActor, cmdKeys)
        seqKeys = translate.seqKeys(cmdKeys)
        __, duplicate = translate.spsExposureKeys(cmdKeys, doRaise=False)
        lampsKeys = translate.lampsKeys(cmdKeys)
        lampsKeys.update(iicActor.engine.keyRepo.getNirTiming(cams))

        return cls(cams, lampsKeys, duplicate, **seqKeys)


class Flats(TimedLampsSequence):
    """ Biases sequence """
    seqtype = 'flats'
    exptype = 'flat'

    def __init__(self, cams, lampsKeys, duplicate, windowKeys, **seqKeys):
        SpsSequence.__init__(self, cams, isWindowed=bool(windowKeys), **seqKeys)

        self.expose(self.exptype, lampsKeys, cams, duplicate=duplicate, windowKeys=windowKeys)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        cams = SpsSequence.keysToCam(iicActor, cmdKeys)
        seqKeys = translate.seqKeys(cmdKeys)
        __, duplicate = translate.spsExposureKeys(cmdKeys, doRaise=False)
        windowKeys = translate.windowKeys(cmdKeys)
        lampsKeys = translate.lampsKeys(cmdKeys)

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
        cams = SpsSequence.keysToCam(iicActor, cmdKeys)
        seqKeys = translate.seqKeys(cmdKeys)
        __, duplicate = translate.spsExposureKeys(cmdKeys, doRaise=False)

        return cls(cams, duplicate, **seqKeys)


class DitheredArcs(TimedLampsSequence):
    """ Dithered Arcs sequence """
    seqtype = 'ditheredArcs'

    def __init__(self, cams, lampsKeys, duplicate, pixelStep, slitControl, **seqKeys):
        SpsSequence.__init__(self, cams, **seqKeys)
        # start hexapod and move home.
        slitControl.start(self, cams)
        self.add('sps', 'slit home', cams=cams)

        end = int(1 / pixelStep)
        start = 0
        for x in range(start, end):
            for y in range(start, end):
                xPix, yPix = x * pixelStep, y * pixelStep
                self.add('sps', 'slit dither', x=xPix, y=yPix, pixels=True, abs=True, cams=cams)
                self.expose('arc', lampsKeys, cams, duplicate=duplicate)

        # move back home and stop hexapod, even if the sequence fails.
        self.tail.add('sps', 'slit home', cams=cams)
        # Turn back off the hexapods this sequence powered on.
        slitControl.stop(self.tail)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        cams = SpsSequence.keysToCam(iicActor, cmdKeys)
        seqKeys = translate.seqKeys(cmdKeys)
        __, duplicate = translate.spsExposureKeys(cmdKeys, doRaise=False)
        lampsKeys = translate.lampsKeys(cmdKeys)
        pixelStep = cmdKeys['pixelStep'].values[0]

        slitControl = SlitControl.fromConfig(iicActor, cams, cmdKeys, cls.seqtype)
        lampsKeys.update(iicActor.engine.keyRepo.getNirTiming(cams))

        return cls(cams, lampsKeys, duplicate, pixelStep, slitControl, **seqKeys)


class DefocusedArcs(TimedLampsSequence):
    """ Defocus sequence """
    seqtype = 'defocusedArcs'

    def __init__(self, cams, lampsKeys, iisKeys, duplicate, positions, slitControl, **seqKeys):
        SpsSequence.__init__(self, cams, **seqKeys)
        # start hexapod and move home.
        slitControl.start(self, cams)
        self.add('sps', 'slit home', cams=cams)
        # the H4 timing rides along with the lamps keys, but is not a lamp time to scale.
        nirTiming = dict([(key, lampsKeys[key]) for key in ('h4ReadTime', 'h4IrpRatio') if key in lampsKeys])

        for position in positions:
            multFactor, _ = defocused_exposure_times_single_position(exp_time_0=1, att_value_0=None,
                                                                     defocused_value=position)
            # a plain int, so the scaled keys stay python ints once parsed into commands.
            multFactor = int(multFactor)

            scaled = dict([(lamp, exptime * multFactor) for lamp, exptime in lampsKeys.items() if lamp not in nirTiming])
            scaled['iis'] = dict([(lamp, exptime * multFactor) for lamp, exptime in iisKeys.items()])
            scaled.update(nirTiming)

            self.add('sps', 'slit', focus=position, abs=True, cams=cams)
            self.expose('arc', scaled, cams, duplicate=duplicate)

        # move back home and stop hexapod, even if the sequence fails.
        self.tail.add('sps', 'slit home', cams=cams)
        # Turn back off the hexapods this sequence powered on.
        slitControl.stop(self.tail)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        cams = SpsSequence.keysToCam(iicActor, cmdKeys)
        seqKeys = translate.seqKeys(cmdKeys)
        __, duplicate = translate.spsExposureKeys(cmdKeys, doRaise=False)
        lampsKeys = translate.lampsKeys(cmdKeys)
        iisKeys = lampsKeys.pop('iis', None)  # removing iis for now.
        start, stop, num = cmdKeys['position'].values
        positions = np.linspace(start, stop, num=int(num)).round(6)

        slitControl = SlitControl.fromConfig(iicActor, cams, cmdKeys, cls.seqtype)
        lampsKeys.update(iicActor.engine.keyRepo.getNirTiming(cams))

        return cls(cams, lampsKeys, iisKeys, duplicate, positions, slitControl, **seqKeys)


class FpaThroughFocus(TimedLampsSequence):
    """ FpaThroughFocus sequence. """
    seqtype = 'fpaThroughFocus'

    def __init__(self, cams, lampsKeys, duplicate, positions, **seqKeys):
        SpsSequence.__init__(self, cams, **seqKeys)

        for microns in positions:
            # we do a relative move to focus position.
            self.add('sps', 'fpa moveFocus', microns=microns, abs=False, cams=cams)
            self.expose('arc', lampsKeys, cams, duplicate=duplicate)

        # moving back to focus at the end.
        self.tail.add('sps', 'fpa toFocus', cams=cams)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        cams = SpsSequence.keysToCam(iicActor, cmdKeys)
        seqKeys = translate.seqKeys(cmdKeys)
        __, duplicate = translate.spsExposureKeys(cmdKeys, doRaise=False)
        lampsKeys = translate.lampsKeys(cmdKeys)
        lampsKeys.update(iicActor.engine.keyRepo.getNirTiming(cams))
        start, stop, num = cmdKeys['micronsRange'].values
        positions = np.linspace(start, stop, num=int(num)).round(6)

        return cls(cams, lampsKeys, duplicate, positions, **seqKeys)
