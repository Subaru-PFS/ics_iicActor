import ics.iicActor.utils.translate as translate
import ics.utils.cmd as cmdUtils
from ics.iicActor.utils.visited import VisitedSequence


class FpsSequence(VisitedSequence):
    caller = 'fps'

    def __init__(self, *args, doTurnOnIlluminator=False, cableBLampOn=False, useMcsBiaControl=True, **kwargs):
        super().__init__(*args, **kwargs)

        if doTurnOnIlluminator:
            self.turnOnIlluminators(cableBLampOn, useMcsBiaControl)
            self.turnOffIlluminators(cableBLampOn, useMcsBiaControl)

    def turnOnIlluminators(self, cableBLampOn=False, useMcsBiaControl=True):
        """Turn on the cobra illuminators.

        With useMcsBiaControl, the bia is not turned on here, mcs is just allowed to drive it itself,
        eg turning it on just before integrating and off as soon as the exposure is over.
        """
        if useMcsBiaControl:
            self.add('mcs', 'biaControl on')
        else:
            self.add('sps', 'bia on')

        self.add('peb', 'led on')

        if cableBLampOn:
            self.add('dcb', 'power on cableB')

    def turnOffIlluminators(self, cableBLampOn=False, useMcsBiaControl=True):
        """Turn off the cobra illuminators."""
        if useMcsBiaControl:
            self.tail.add('mcs', 'biaControl off')
        else:
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
    def frameIds(self):
        """The MCS frames the loop exposed successfully."""
        return [int(cmdUtils.findCmdKeyValue(subCmd.cmdStr, 'frameId')) for subCmd in self.cmdList
                if subCmd.actor == 'mcs' and subCmd.cmdHead == 'expose' and subCmd.cmdRet.succeed]

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

    def addReduce(self, frameIds):
        """Close out the current boresight acquisition loop and process the data."""
        self.append('fps', 'calculateBoresight', frameIds=frameIds, writeToDB=True, timeLim=30)


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
                 skipFiducialInterferenceCheck, maskFile=False, dotTarget=None, dotLanding=None, dotCalib=None,
                 aimLanding=False, **fpsKeys):
        super().__init__(**fpsKeys)

        # The black-dot depths and calibration are fps's own unless a sequence names them.
        dotKeys = {name: value for name, value in (('dotTarget', dotTarget), ('dotLanding', dotLanding),
                                                   ('dotCalib', dotCalib))
                   if value is not None}

        # move to pfsDesign.
        self.add('fps', 'moveToPfsDesign', parseVisit=True, designId=designId, iteration=nIteration,
                 tolerance=tolerance, maskFile=maskFile, exptime=exptime, goHome=not noHome, twoStepsOff=twoStepsOff,
                 shortExpOff=shortExpOff, noTweak=noTweak, skipFiducialInterferenceCheck=skipFiducialInterferenceCheck,
                 aimLanding=aimLanding, **dotKeys, timeLim=600)

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


class BlindMoveRun(MoveToPfsDesign):
    """A convergence on turned black dots, then the frame that measures its two blind moves.

    On a design whose dots are turned into view of MCS (fps createBlackDotDesign
    dotThetaOffset=), fps measureBlindMove records the landing and the push of every dot
    cobra in opdb cobra_blind_move, for fps calibrateBlindMove and validateBlindMove.
    """
    seqtype = 'blindMoveRun'

    configKeys = ('nIteration', 'tolerance', 'exptime', 'noHome', 'twoStepsOff', 'shortExpOff', 'noTweak',
                  'skipFiducialInterferenceCheck')
    """The keys of the calibrateBlindMove config section a run takes.  The run lands at fps'
    convergence.dotLanding and pushes to its dotTarget; the calibration and aimLanding are
    given per run."""

    def __init__(self, designId, exptime, **kwargs):
        super().__init__(designId, exptime=exptime, **kwargs)

        self.add('fps', 'measureBlindMove', timeLim=60 + exptime)


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
