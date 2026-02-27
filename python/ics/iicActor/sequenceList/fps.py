import ics.iicActor.utils.translate as translate
from ics.iicActor.utils.visited import VisitedSequence


class FpsSequence(VisitedSequence):
    caller = 'fps'

    def __init__(self, *args, doTurnOnIlluminator=False, cableBLampOn=False, **kwargs):
        super().__init__(*args, **kwargs)

        if doTurnOnIlluminator:
            self.turnOnIlluminators(cableBLampOn)
            self.turnOffIlluminators(cableBLampOn)

    def turnOnIlluminators(self, cableBLampOn=False):
        """Turn on the cobra illuminators."""
        self.add('sps', 'bia on')
        self.add('peb', 'led on')

        if cableBLampOn:
            self.add('dcb', 'power on cableB')

    def turnOffIlluminators(self, cableBLampOn=False):
        """Turn off the cobra illuminators."""
        self.tail.add('sps', 'bia off')
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
                 maskFile=False, **fpsKeys):
        super().__init__(**fpsKeys)

        # move to pfsDesign.
        self.add('fps', 'moveToPfsDesign', parseVisit=True, designId=designId, iteration=nIteration,
                 tolerance=tolerance, maskFile=maskFile, exptime=exptime, goHome=not noHome, twoStepsOff=twoStepsOff,
                 shortExpOff=shortExpOff, noTweak=noTweak, timeLim=600)

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


class DotCrossing(FpsSequence):
    """ fps cobraMoveSteps crossing loop. """
    seqtype = 'dotCrossing'

    def __init__(self, exptime, count, stepSize, **fpsKeys):
        super().__init__(**fpsKeys)

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
        dotCrossingConfig = translate.resolveCmdConfig(cmdKeys, iicActor.actorConfig, 'dotCrossing')

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

        self.add('mcs', 'expose object', exptime=exptime, parseFrameId=True, doFibreId=True)
        self.add('fps', 'genPfsConfigFromMcs', parseVisit=True, designId=designId)

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

        self.add('fps', f'cobraMoveAngles', phi=phi, theta=theta, angle=angle, maskFile=maskFile)

        if genPfsConfig:
            self.add('mcs', 'expose object', exptime=exptime, parseFrameId=True, doFibreId=True)
            self.add('fps', 'genPfsConfigFromMcs', parseVisit=True, designId=designId)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys, designId):
        """Defining rules to construct FpsLoop object."""
        seqKeys = translate.seqKeys(cmdKeys)

        phi = 'phi' in cmdKeys
        theta = 'theta' in cmdKeys
        angle = cmdKeys['angle'].values[0]
        maskFile = translate.getMaskFilePathFromCmd(cmdKeys, iicActor.actorConfig)

        genPfsConfig = 'genPfsConfig' in cmdKeys
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
            self.add('mcs', 'expose object', exptime=exptime, parseFrameId=True, doFibreId=True)
            self.add('fps', 'genPfsConfigFromMcs', parseVisit=True, designId=designId)

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
