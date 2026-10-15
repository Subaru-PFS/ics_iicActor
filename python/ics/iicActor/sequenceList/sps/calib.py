import math

import ics.iicActor.utils.translate as translate
from ics.iicActor.sequenceList.sps.base import Biases, Darks, Arcs, Flats
from ics.iicActor.sps.sequence import SpsSequence
from ics.iicActor.sps.slitControl import SlitControl
from ics.iicActor.sps.timedLamps import TimedLampsSequence
from ics.iicActor.utils.subcmd import Wait
from ics.utils.sps.exposureTiming import ExposureTiming


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

    def __init__(self, cams, lampsKeys, positions, duplicate, slitControl, interleaveDark, **seqKeys):
        SpsSequence.__init__(self, cams, **seqKeys)

        # taking a trace before starting hexapod, (for the one that were off in the first place).
        camsPoweredOff = slitControl.selectCams(cams, slitControl.poweredOff)
        if camsPoweredOff:
            self.takeOneDuplicate(lampsKeys, camsPoweredOff, duplicate, interleaveDark)

        # taking a trace in home to start.
        slitControl.start(self, cams)
        self.add('sps', 'slit home', cams=cams)
        self.takeOneDuplicate(lampsKeys, cams, duplicate, interleaveDark)

        for position in positions:
            self.add('sps', 'slit dither', x=position, pixels=True, abs=True, cams=cams)
            self.takeOneDuplicate(lampsKeys, cams, duplicate, interleaveDark)

        # taking a trace in home to end.
        self.add('sps', 'slit home', cams=cams)
        self.takeOneDuplicate(lampsKeys, cams, duplicate, interleaveDark)

        # taking a trace after the hexapod is turned back off (for the one that this sequence powered on).
        slitControl.stop(self)
        camsStopped = slitControl.selectCams(cams, slitControl.toStop)
        if camsStopped:
            self.takeOneDuplicate(lampsKeys, camsStopped, duplicate, interleaveDark)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        cams = SpsSequence.keysToCam(iicActor, cmdKeys)
        seqKeys = translate.seqKeys(cmdKeys)
        __, duplicate = translate.spsExposureKeys(cmdKeys, doRaise=False)
        lampsKeys = translate.lampsKeys(cmdKeys)
        positions = translate.ditheredFlatsKeys(cmdKeys)

        slitControl = SlitControl.fromConfig(iicActor, cams, cmdKeys, cls.seqtype)
        interleaveDark = cmdKeys['interleaveDark'].values[0] if 'interleaveDark' in cmdKeys else False

        return cls(cams, lampsKeys, positions, duplicate, slitControl, interleaveDark, **seqKeys)

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
    exptype = 'sciflat'

    def __init__(self, cams, lampsKeys, positions, duplicate, slitControl, interleaveDark, nTraceBefore, nTraceAfter,
                 **seqKeys):
        SpsSequence.__init__(self, cams, **seqKeys)

        # taking a trace in home to start.
        slitControl.start(self, cams)
        self.add('sps', 'slit home', cams=cams)
        # taking nTraceBefore images in home first.
        self.takeOneDuplicate(lampsKeys, cams, int(duplicate * nTraceBefore), interleaveDark)

        for position in positions:
            self.add('sps', 'slit dither', x=position, pixels=True, abs=True, cams=cams)
            self.takeOneDuplicate(lampsKeys, cams, duplicate, interleaveDark)

        # taking a trace in home to end.
        self.add('sps', 'slit home', cams=cams)
        self.takeOneDuplicate(lampsKeys, cams, int(duplicate * nTraceAfter), interleaveDark)

        # Turn back off the hexapods powered on, unless deferred.
        slitControl.stop(self)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys, keepHexapodOn=False):
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

        slitControl = SlitControl.fromConfig(iicActor, cams, cmdKeys, cls.seqtype, keepHexapodOn=keepHexapodOn)

        return cls(cams, lampsKeys, positions, duplicate, slitControl, interleaveDark, nTraceBefore, nTraceAfter,
                   **seqKeys)

    def takeOneDuplicate(self, lampsKeys, cams, duplicate, interleaveDark):
        """take one duplicate, interleave for nir arm if necessary."""
        nirCam = [cam for cam in cams if cam.arm == 'n']

        for i in range(duplicate):
            self.expose(self.exptype, lampsKeys, cams, duplicate=1)
            # interleave dark for nir.
            if nirCam and interleaveDark:
                SpsSequence.expose(self, 'dark', interleaveDark, nirCam, duplicate=1)

    def setComments(self, rdaPosition):
        """Setting default comments."""
        self.comments = 'brn arm' if rdaPosition == 'low' else 'bmn arm'


class ShutterDriftFlats(SpsSequence):
    """ Dithered Flats sequence """
    seqtype = 'driftFlats'

    def __init__(self, cams, exptime, duplicate, pixMin, pixMax, slitControl, **seqKeys):
        SpsSequence.__init__(self, cams, **seqKeys)

        # go home first.
        slitControl.start(self, cams)

        for iDuplicate in range(duplicate):
            # moving to the beginning of the range // required for N.
            self.add('sps', 'slit dither', x=pixMin, pixels=True, abs=True, cams=cams)
            self.expose('flat', exptime, cams, duplicate=1, slideSlit=f'{pixMin:.1f},{pixMax:.1f}')

        # move back home
        self.tail.add('sps', 'slit home', cams=cams)
        # Turn back off the hexapods powered on, unless deferred.
        slitControl.stop(self.tail)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        cams = SpsSequence.keysToCam(iicActor, cmdKeys)
        seqKeys = translate.seqKeys(cmdKeys)
        exptime, duplicate = translate.spsExposureKeys(cmdKeys)

        pixMin, pixMax, num = cmdKeys['pixelRange'].values
        slitControl = SlitControl.fromConfig(iicActor, cams, cmdKeys, cls.seqtype)

        return cls(cams, exptime, duplicate, pixMin, pixMax, slitControl, **seqKeys)


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
        slitControl = SlitControl.fromConfig(iicActor, cams, cmdKeys, cls.seqtype)

        return cls(cams, lampsKeys, duplicate, pixMin, pixMax, slitControl, **seqKeys)


class ScienceArc(Arcs):
    """ Biases sequence """
    seqtype = 'scienceArc'
    exptype = 'sciarc'
    doScienceCheck = True


class ScienceTrace(Flats):
    """ Biases sequence """
    seqtype = 'scienceTrace'
    exptype = 'sciflat'
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


class QuartzLadder(SpsSequence):
    """Quartz exposure-time ladder, measuring the detector response against signal level.

    One block per exposure time X: a bias, then shutter-timed flats reference, X x duplicate, reference, all within one
    quartz lamp-on period, so lamp drift within a block cancels by interpolating the references. A last bias closes the
    ladder, each block's bias closing the previous one.
    """
    seqtype = 'quartzLadder'
    # [s] lamp time beyond the exposure timing model; the lamp is stopped at the end of each block anyway.
    lampMargin = 30

    def __init__(self, cams, exptimes, reference, duplicate, settleTime, h4ReadTime=None, h4IrpRatio=None,
                 **seqKeys):
        SpsSequence.__init__(self, cams, **seqKeys)
        arms = set([cam.arm for cam in cams])

        for iBlock, exptime in enumerate(exptimes):
            blockExptimes = [reference] + [exptime] * duplicate + [reference]
            blockSettleTime = settleTime if iBlock == 0 else 0
            lampTime = QuartzLadder.lampTime(blockExptimes, arms, blockSettleTime,
                                             h4ReadTime=h4ReadTime, h4IrpRatio=h4IrpRatio)

            self.expose('bias', 0, cams)

            self.add('lamps', f'prepare halogen={lampTime}')
            self.add('lamps', 'waitForReadySignal', timeLim=240)
            self.add('lamps', 'go noWait')

            if blockSettleTime:
                list.append(self, Wait(self, blockSettleTime))

            self.expose('flat', blockExptimes, cams)
            self.add('lamps', 'stop')

        self.expose('bias', 0, cams)

    @staticmethod
    def lampTime(exptimes, arms, settleTime, h4ReadTime=None, h4IrpRatio=None, roundToSecs=5):
        """How long the quartz must burn for one block, in seconds.

        From the lamp go to the last shutter close, from the exposure timing model shared with sps, plus `lampMargin`,
        rounded up to the next multiple of `roundToSecs`.

        Parameters
        ----------
        exptimes : `list` of `float`
            Exposure times of the block, in order.
        arms : iterable of `str`
            Exposed arms, among b, r, m and n.
        settleTime : `float`
            Wait between the lamp go and the first exposure.
        h4ReadTime, h4IrpRatio : `float`, `int`
            H4 read time and IRP ratio, required with the n arm.
        """
        exposureTiming = ExposureTiming.fromInstdata()
        allButLast = sum([exposureTiming.exposureTime(exptime, arms, readTime=h4ReadTime, irpRatio=h4IrpRatio)
                          for exptime in exptimes[:-1]])
        last = exposureTiming.lampOnTime(exptimes[-1], arms, readTime=h4ReadTime, irpRatio=h4IrpRatio)
        totalSecs = settleTime + allButLast + last + QuartzLadder.lampMargin

        return int(roundToSecs * math.ceil(totalSecs / roundToSecs))

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct QuartzLadder object, the quartzLadder config completing the command keys."""
        cams = SpsSequence.keysToCam(iicActor, cmdKeys)
        seqKeys = translate.seqKeys(cmdKeys)

        config = iicActor.actorConfig['quartzLadder']
        exptimes = cmdKeys['exptime'].values if 'exptime' in cmdKeys else config['exptime']
        reference = cmdKeys['reference'].values[0] if 'reference' in cmdKeys else config['reference']
        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else config['duplicate']
        settleTime = cmdKeys['settleTime'].values[0] if 'settleTime' in cmdKeys else config['settleTime']
        nirTiming = iicActor.engine.keyRepo.getNirTiming(cams)

        return cls(cams, list(exptimes), reference, duplicate, settleTime, **nirTiming, **seqKeys)
