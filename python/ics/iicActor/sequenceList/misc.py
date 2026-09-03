import ics.iicActor.utils.translate as translate
from ics.iicActor.sequenceList.fps import MoveToPfsDesign, FpsSequence
from ics.iicActor.sps.sequence import SpsSequence
from ics.iicActor.sps.timedLamps import TimedLampsSequence


class FiberIdentification(SpsSequence):
    """ fps MoveToPfsDesign command. """
    seqtype = 'fiberIdentification'

    def __init__(self, cams, exptime, windowKeys, actorConfig, fiberGroups, **seqKeys):
        SpsSequence.__init__(self, cams, **seqKeys)

        self.expose('domeflat', exptime, cams, windowKeys=windowKeys)

        for groupId in fiberGroups:
            self.add('fps', f'cobraMoveSteps phi',
                     stepsize=3000, maskFile=translate.constructMaskFilePath(f'mtpGroup{groupId:02d}', actorConfig))
            # use sps erase command to niet things up.
            self.add('sps', 'erase', cams=cams)
            self.expose('domeflat', exptime, cams, windowKeys=windowKeys)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        cams = SpsSequence.keysToCam(iicActor, cmdKeys)
        seqKeys = translate.seqKeys(cmdKeys)
        # we are using hsc ring lamps.
        windowedFlatConfig = iicActor.actorConfig['windowedFlat']['hscLamps'].copy()
        exptime = windowedFlatConfig.pop('exptime')
        # group 25 does not exist.
        default = list(set(range(2, 32)) - {25})
        fiberGroups = cmdKeys['fiberGroups'].values if 'fiberGroups' in cmdKeys else default

        return cls(cams, exptime, windowedFlatConfig, iicActor.actorConfig, fiberGroups, **seqKeys)


class DotRoachInit(SpsSequence):
    """ fps MoveToPfsDesign command. """
    seqtype = 'dotRoachInit'
    useLamps = 'hscLamps'

    def __init__(self, cams, exptime, **seqKeys):
        SpsSequence.__init__(self, cams, **seqKeys)

        # turning drp processing on
        self.add('drp', 'startDotRoach', cams=cams)

        # full frame first
        self.expose('domeflat', exptime, cams, windowKeys=None)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        cams = SpsSequence.keysToCam(iicActor, cmdKeys)
        seqKeys = translate.seqKeys(cmdKeys)

        windowedFlatConfig = iicActor.actorConfig['windowedFlat'][cls.useLamps]
        exptime = translate.resolveExptime(cmdKeys, windowedFlatConfig)

        return cls(cams, exptime, **seqKeys)


class DotRoach(SpsSequence):
    """Flux-based dot convergence: windowed flat → processDotRoach → moveToDotByFlux, repeated nIteration times."""
    seqtype = 'dotRoachNew'
    useLamps = 'hscLamps'

    configSection = 'dotRoach'
    """actorConfig section holding this sequence's flat count."""

    fullFrameAtEnd = True
    """Close with an unwindowed flat, measured the same way as the windowed ones.

    Every flux in the sequence is a ratio against the full-frame reference taken at the
    start, so a windowed flat and that reference are not read the same way.  Repeating
    the last measurement unwindowed puts the two on the record together, which is the
    only way to see whether the ratio carries a windowing term.  The scan does not need
    it: it is after the shape of the curve, not the level.
    """

    sweep = False
    """Step every dot cobra each flat, rather than only the ones still lit.

    A calibration needs the whole fleet sampled at every depth, so the curve is measured
    where the optimum turns out to be and not only up to it.  A sequence whose job is to
    hide leaves a cobra alone once its flux says it is behind the dot.
    """

    def __init__(self, cams, exptime, windowKeys, nIteration, **seqKeys):
        SpsSequence.__init__(self, cams, **seqKeys)

        sweep = ' sweep' if self.sweep else ''

        for iterNum in range(nIteration):
            nRemaining = nIteration - iterNum
            # Windowed flats do NOT erase the detector (only full-frame does), so an
            # un-erased residual would leak into the flux ratio.  Erase each iteration.
            self.add('sps', 'erase', cams=cams)
            self.expose('domeflat', exptime, cams, windowKeys=windowKeys)
            self.add('drp', 'processDotRoach')
            self.add('fps', f'moveToDotByFlux{sweep} nRemaining={nRemaining}', timeLim=120)

        # Final flux measurement after last move — record only, no cobra movement.
        self.add('sps', 'erase', cams=cams)
        self.expose('domeflat', exptime, cams, windowKeys=windowKeys)
        self.add('drp', 'processDotRoach')
        self.add('fps', f'moveToDotByFlux{sweep} nRemaining=0', timeLim=120)

        if self.fullFrameAtEnd:
            # Full frame reads out erased, so no erase of its own.
            self.expose('domeflat', exptime, cams, windowKeys=None)
            self.add('drp', 'processDotRoach')

        self.add('drp', 'stopDotRoach')

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct DotRoachByFlux object."""
        cams = SpsSequence.keysToCam(iicActor, cmdKeys)
        seqKeys = translate.seqKeys(cmdKeys)

        windowedFlatConfig = iicActor.actorConfig['windowedFlat'][cls.useLamps]
        exptime = translate.resolveExptime(cmdKeys, windowedFlatConfig)
        windowKeys = translate.windowKeys(cmdKeys, windowedFlatConfig)
        # Only nIteration is taken from the section; the rest of it configures the
        # convergence that runs before the flats, which is not this sequence's business.
        config = iicActor.actorConfig.get(cls.configSection,
                                          iicActor.actorConfig['moveToDotByFlux'])
        nIteration = config['nIteration']

        return cls(cams, exptime, windowKeys, nIteration=nIteration, **seqKeys)


class DotScan(DotRoach):
    """The calibration form of the scan: the fleet is walked across the dot in uniform
    steps so the obscuration curve is sampled, rather than stopped once hidden."""
    seqtype = 'dotScan'
    configSection = 'dotScan'
    sweep = True
    fullFrameAtEnd = False


class DotRoachPfiLamps(DotRoach, TimedLampsSequence):
    useLamps = 'pfiLamps'

    # initial exposure
    def expose(self, exptype, exptime, cams, **windowKeys):
        exptime = dict(halogen=int(exptime), shutterTiming=False, iis=dict())

        TimedLampsSequence.expose(self, 'flat', exptime, cams, **windowKeys)


class DotScanPfiLamps(DotScan, TimedLampsSequence):
    useLamps = 'pfiLamps'

    # initial exposure
    def expose(self, exptype, exptime, cams, **windowKeys):
        exptime = dict(halogen=int(exptime), shutterTiming=False, iis=dict())

        TimedLampsSequence.expose(self, 'flat', exptime, cams, **windowKeys)


class DotRoachInitPfiLamps(DotRoachInit, TimedLampsSequence):
    useLamps = 'pfiLamps'

    # initial exposure
    def expose(self, exptype, exptime, cams, **windowKeys):
        exptime = dict(halogen=int(exptime), shutterTiming=False, iis=dict())

        TimedLampsSequence.expose(self, 'flat', exptime, cams, **windowKeys)
