import ics.iicActor.utils.translate as translate
from ics.iicActor.utils.visited import VisitedSequence


class FpsSequence(VisitedSequence):
    caller = 'fps'

    def __init__(self, *args, doTurnOnIlluminator=False, cableBLampOn=False, useBiaCallback=True, **kwargs):
        super().__init__(*args, **kwargs)

        if doTurnOnIlluminator:
            self.turnOnIlluminators(cableBLampOn, useBiaCallback)
            self.turnOffIlluminators(cableBLampOn, useBiaCallback)

    def turnOnIlluminators(self, cableBLampOn=False, useBiaCallback=True):
        """Turn on the cobra illuminators."""
        self.add('sps', 'bia callbackOn' if useBiaCallback else 'bia on')
        self.add('peb', 'led on')

        if cableBLampOn:
            self.add('dcb', 'power on cableB')

    def turnOffIlluminators(self, cableBLampOn=False, useBiaCallback=True):
        """Turn off the cobra illuminators."""
        self.tail.add('sps', 'bia callbackOff' if useBiaCallback else 'bia off')
        self.tail.add('peb', 'led off')

        if cableBLampOn:
            self.tail.add('dcb', 'power off cableB')


class BoresightLoop(FpsSequence):
    """The state required to run a boresight measurement loop.

    Basically, the Gen2 command knows about the telescope motion, and
    interleaves POPT2 rotations with requests to us to expose. At the
    end we are commanded to read the data and generate a new boresight.

    """
    seqtype = 'boresightLoop'

    def __init__(self, exptime, nExposures, **fpsKeys):
        super().__init__(**fpsKeys)

        self.exptime = exptime
        self.nExposures = nExposures

    @property
    def startFrame(self):
        return self.visit.visitId * 100

    @property
    def endFrame(self):
        return self.visit.visitId * 100 + self.visit.frameId() - 1

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct BoresightLoop object."""
        seqKeys = translate.seqKeys(cmdKeys)

        exptime = translate.resolveMcsExptime(cmdKeys, iicActor.actorConfig)
        nExposures = cmdKeys['nExposures'].values[0] if 'nExposures' in cmdKeys else 2
        illuminators = translate.illuminatorKeys(iicActor.actorConfig)

        return cls(exptime, nExposures, **illuminators, **seqKeys)

    def addPosition(self):
        """Acquire data for a new boresight position."""
        for i in range(self.nExposures):
            self.append('mcs', 'expose object', exptime=self.exptime, frameId=self.visit.nextFrameId(), doFibreId=True)

    def addReduce(self, startFrame, endFrame):
        """Close out the current boresight acquisition loop and process the data."""
        self.append('fps', 'calculateBoresight', startFrame=startFrame, endFrame=endFrame, timeLim=30)


class FpsLoop(FpsSequence):
    """Run an MCS+FPS loop, without moving cobras."""
    seqtype = 'fpsLoop'

    def __init__(self, exptime, cnt, **fpsKeys):
        super().__init__(**fpsKeys)

        timeLim = 30 + (15 + exptime) * cnt
        self.add('fps', 'testLoop', parseVisit=True, exptime=exptime, cnt=cnt, timeLim=timeLim)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct FpsLoop object."""
        seqKeys = translate.seqKeys(cmdKeys)

        exptime = translate.resolveMcsExptime(cmdKeys, iicActor.actorConfig)
        cnt = cmdKeys['cnt'].values[0] if 'cnt' in cmdKeys else 1
        illuminators = translate.illuminatorKeys(iicActor.actorConfig)

        return cls(exptime, cnt, **seqKeys, **illuminators)


class MoveToPfsDesign(FpsSequence):
    """ fps MoveToPfsDesign command. """
    seqtype = 'moveToPfsDesign'

    def __init__(self, designId, nIteration, tolerance, exptime, noHome, twoStepsOff, shortExpOff, noTweak,
                 skipFiducialInterferenceCheck, maskFile=False, dotTarget=None, dotLanding=None,
                 noBlindMove=False, **fpsKeys):
        super().__init__(**fpsKeys)

        # The depths are fps defaults unless a sequence names them: a dot cobra rides the
        # ramp to dotLanding and is pushed from there to dotTarget.
        dotKeys = {name: value for name, value in (('dotTarget', dotTarget),
                                                   ('dotLanding', dotLanding))
                   if value is not None}

        # move to pfsDesign.
        self.add('fps', 'moveToPfsDesign', parseVisit=True, designId=designId, iteration=nIteration,
                 tolerance=tolerance, maskFile=maskFile, exptime=exptime, goHome=not noHome, twoStepsOff=twoStepsOff,
                 shortExpOff=shortExpOff, noTweak=noTweak, skipFiducialInterferenceCheck=skipFiducialInterferenceCheck,
                 noBlindMove=noBlindMove, **dotKeys, timeLim=600)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys, designId):
        seqKeys = translate.seqKeys(cmdKeys)

        # maskFile = translate.getMaskFilePathFromCmd(cmdKeys, iicActor.actorConfig)
        # Removing maskFile for now, it's broken on fps side (per INSTRM-2192)
        maskFile = False

        moveToPfsDesignConfig = translate.resolveCmdConfig(cmdKeys, iicActor.actorConfig, 'moveToPfsDesign')
        illuminators = translate.illuminatorKeys(iicActor.actorConfig)

        return cls(designId, maskFile=maskFile, **moveToPfsDesignConfig, **seqKeys, **illuminators)


class MoveToHome(FpsSequence):
    """ fps MoveToHome command."""
    seqtype = 'moveToHome'

    def __init__(self, exptime, designId, noMCSexposure=False, phi=False, theta=False, all=False, parseVisit=True,
                 **fpsKeys):
        super().__init__(**fpsKeys)

        # move cobras to home, not supposed to, but meh.
        self.add('fps', 'moveToHome', phi=phi, theta=theta, all=all,
                 parseVisit=parseVisit, exptime=exptime, designId=designId, noMCSexposure=noMCSexposure,
                 timeLim=120)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys, designId):
        seqKeys = translate.seqKeys(cmdKeys)
        exptime = translate.resolveMcsExptime(cmdKeys, iicActor.actorConfig)

        noMCSexposure = 'noMCSexposure' in cmdKeys
        parseVisit = not noMCSexposure or 'genPfsConfig' in cmdKeys
        phi = 'phi' in cmdKeys
        theta = 'theta' in cmdKeys
        all = 'all' in cmdKeys or (not phi and not theta)

        illuminators = translate.illuminatorKeys(iicActor.actorConfig)

        return cls(exptime, designId, noMCSexposure, phi, theta, all, parseVisit, **seqKeys, **illuminators)


class NearDotConvergence(MoveToPfsDesign):
    seqtype = 'nearDotConvergence'

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys, designId):
        """Defining rules to construct NearDotConvergence object."""
        seqKeys = translate.seqKeys(cmdKeys)

        maskFile = translate.getMaskFilePathFromCmd(cmdKeys, iicActor.actorConfig)
        illuminators = translate.illuminatorKeys(iicActor.actorConfig)
        nearDotConvergenceConfig = translate.resolveCmdConfig(cmdKeys, iicActor.actorConfig, 'nearDotConvergence')
        return cls(designId, maskFile=maskFile, **nearDotConvergenceConfig, **seqKeys, **illuminators)


class BlindTest(MoveToPfsDesign):
    """Ramp onto the black dots and push to a fixed depth, then look at where it landed.

    The push is the one move a dot run never measures, success putting the fibre out of
    sight; driven against dots declared somewhere the fibre is not occluded, it is the
    move this sequence exists to record.
    """
    seqtype = 'blindTest'

    def __init__(self, designId, exptime, **kwargs):
        super().__init__(designId, exptime=exptime, **kwargs)

        # A frame of fps's own, after the convergence has written its pfsConfig so it
        # cannot become the iteration that is finalised from.  nRemaining=0 measures and
        # steps nothing, the push having already happened.
        self.add('fps', 'moveToDotByFluxFake', nRemaining=0, timeLim=60 + exptime)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys, designId):
        """Defining rules to construct BlindTest object."""
        seqKeys = translate.seqKeys(cmdKeys)

        maskFile = translate.getMaskFilePathFromCmd(cmdKeys, iicActor.actorConfig)
        illuminators = translate.illuminatorKeys(iicActor.actorConfig)
        blindTestConfig = translate.resolveCmdConfig(cmdKeys, iicActor.actorConfig, 'blindTest')

        return cls(designId, maskFile=maskFile, **blindTestConfig, **seqKeys, **illuminators)


class DotScanFake(MoveToPfsDesign):
    """Walk the dot cobras across their dots a fraction at a time, measuring each depth.

    The ramp lands and the fleet stays there, every step after it being one the frames
    record; a scan behind a real dot has to infer those depths from the light blocked.
    """
    seqtype = 'dotScanFake'

    def __init__(self, designId, exptime, nScanSteps, **kwargs):
        super().__init__(designId, exptime=exptime, **kwargs)

        # One frame per depth, nRemaining counting down so the last measures and steps
        # nothing.  Nothing steers the scan: the frames record where the open loop got
        # to, which is the whole of what a scan behind a dot cannot see.
        for nRemaining in range(nScanSteps, -1, -1):
            self.add('fps', 'moveToDotByFluxFake', nRemaining=nRemaining,
                     timeLim=60 + exptime)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys, designId):
        """Defining rules to construct DotScanFake object."""
        seqKeys = translate.seqKeys(cmdKeys)

        maskFile = translate.getMaskFilePathFromCmd(cmdKeys, iicActor.actorConfig)
        illuminators = translate.illuminatorKeys(iicActor.actorConfig)
        config = translate.resolveCmdConfig(cmdKeys, iicActor.actorConfig, 'dotScanFake')

        return cls(designId, maskFile=maskFile, **config, **seqKeys, **illuminators)


class DotCrossing(FpsSequence):
    """ fps cobraMoveSteps crossing loop. """
    seqtype = 'dotCrossing'

    def __init__(self, exptime, count, stepSize, **fpsKeys):
        super().__init__(**fpsKeys)

        if self.seqtype=='phiCrossing':
            stepSize = abs(stepSize)

        if not hasattr(self, 'motor'):
            raise AttributeError('DotCrossing subclasses must define motor')

        self.add('mcs', 'expose object', parseFrameId=True, exptime=exptime, doFibreId=True)

        for iterNum in range(count):
            self.add('fps', f'cobraMoveSteps {self.motor}', stepsize=stepSize)
            self.add('mcs', 'expose object', parseFrameId=True, exptime=exptime, doFibreId=True)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct DotCrossing object."""
        seqKeys = translate.seqKeys(cmdKeys)

        illuminators = translate.illuminatorKeys(iicActor.actorConfig)
        dotCrossingConfig = translate.resolveCmdConfig(cmdKeys, iicActor.actorConfig, cls.seqtype)

        return cls(**dotCrossingConfig, **seqKeys, **illuminators)


class PhiCrossing(DotCrossing):
    motor = 'phi'
    seqtype = 'phiCrossing'


class ThetaCrossing(DotCrossing):
    motor = 'theta'
    seqtype = 'thetaCrossing'


class GenPfsConfigFromMcs(FpsSequence):
    """ fps MoveToPfsDesign command. """
    seqtype = 'genPfsConfigFromMcs'

    def __init__(self, exptime, designId, **fpsKeys):
        super().__init__(**fpsKeys)

        self.add('fps', 'genPfsConfigFromMcs', parseVisit=True, designId=designId, expTime=exptime)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys, designId):
        """Defining rules to construct DotCrossing object."""
        seqKeys = translate.seqKeys(cmdKeys)

        exptime = translate.resolveMcsExptime(cmdKeys, iicActor.actorConfig)
        illuminators = translate.illuminatorKeys(iicActor.actorConfig)

        return cls(exptime, designId, **seqKeys, **illuminators)


class GenBlackDotsConfig(GenPfsConfigFromMcs):
    seqtype = 'genBlackDotsPfsConfig'


class CobraMoveAngles(FpsSequence):
    """ fps MotorOntimeSearch command. """
    seqtype = 'cobraMoveAngles'

    def __init__(self, phi, theta, angle, maskFile, genPfsConfig, exptime, designId, **fpsKeys):
        super().__init__(**fpsKeys)

        self.add('fps', f'cobraMoveAngles', phi=phi, theta=theta, angle=angle, maskFile=maskFile,
                 genPfsConfig=genPfsConfig, designId=designId)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys, designId):
        """Defining rules to construct FpsLoop object."""
        seqKeys = translate.seqKeys(cmdKeys)

        phi = 'phi' in cmdKeys
        theta = 'theta' in cmdKeys
        angle = cmdKeys['angle'].values[0]
        maskFile = translate.getMaskFilePathFromCmd(cmdKeys, iicActor.actorConfig)

        genPfsConfig = 'genPfsConfig' in cmdKeys
        designId = designId if genPfsConfig else None
        exptime = translate.resolveMcsExptime(cmdKeys, iicActor.actorConfig)
        illuminators = translate.illuminatorKeys(iicActor.actorConfig)

        return cls(phi, theta, angle, maskFile, genPfsConfig, exptime, designId, **seqKeys, **illuminators)


class CobraMoveSteps(FpsSequence):
    """ fps MotorOntimeSearch command. """
    seqtype = 'cobraMoveSteps'

    def __init__(self, phi, theta, stepSize, maskFile, genPfsConfig, exptime, designId, **fpsKeys):
        super().__init__(**fpsKeys)

        self.add('fps', f'cobraMoveSteps', phi=phi, theta=theta, stepsize=stepSize, maskFile=maskFile)

        if genPfsConfig:
            self.add('fps', 'genPfsConfigFromMcs', parseVisit=True, designId=designId, expTime=exptime)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys, designId):
        """Defining rules to construct FpsLoop object."""
        seqKeys = translate.seqKeys(cmdKeys)

        phi = 'phi' in cmdKeys
        theta = 'theta' in cmdKeys
        stepSize = cmdKeys['stepsize'].values[0]
        maskFile = translate.getMaskFilePathFromCmd(cmdKeys, iicActor.actorConfig)

        genPfsConfig = 'genPfsConfig' in cmdKeys
        exptime = translate.resolveMcsExptime(cmdKeys, iicActor.actorConfig)
        illuminators = translate.illuminatorKeys(iicActor.actorConfig)

        return cls(phi, theta, stepSize, maskFile, genPfsConfig, exptime, designId, **seqKeys, **illuminators)
