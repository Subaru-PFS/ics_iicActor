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

    def __init__(self, cams, exptime, windowKeys, nIteration, **seqKeys):
        SpsSequence.__init__(self, cams, **seqKeys)

        for iterNum in range(nIteration):
            nRemaining = nIteration - iterNum
            self.expose('domeflat', exptime, cams, windowKeys=windowKeys)
            self.add('drp', 'processDotRoach')
            self.add('fps', f'moveToDotByFlux nRemaining={nRemaining}', timeLim=120)

        # Final flux measurement after last move.
        self.expose('domeflat', exptime, cams, windowKeys=windowKeys)
        self.add('drp', 'processDotRoach')
        self.add('drp', 'stopDotRoach')

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct DotRoachByFlux object."""
        cams = SpsSequence.keysToCam(iicActor, cmdKeys)
        seqKeys = translate.seqKeys(cmdKeys)

        windowedFlatConfig = iicActor.actorConfig['windowedFlat'][cls.useLamps].copy()
        exptime = windowedFlatConfig.pop('exptime')
        config = translate.resolveCmdConfig(cmdKeys, iicActor.actorConfig, 'moveToDotByFlux')

        return cls(cams, exptime, windowedFlatConfig, **config, **seqKeys)


class DotRoachPfiLamps(DotRoach, TimedLampsSequence):
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
