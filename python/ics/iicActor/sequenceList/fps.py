import ics.iicActor.utils.translate as translate
from ics.iicActor.utils.visited import VisitedSequence


class FpsSequence(VisitedSequence):
    caller = 'fps'

    def __init__(self, *args, doTurnOnIlluminator=False, cableBLampOn=False, **kwargs):
        VisitedSequence.__init__(self, *args, **kwargs)

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

    def __init__(self, exptime, nExposures, cableBLampOn, **seqKeys):
        FpsSequence.__init__(self, doTurnOnIlluminator=True, cableBLampOn=cableBLampOn, **seqKeys)

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

        exptime = cmdKeys['exptime'].values[0] if 'exptime' in cmdKeys else 2.0
        nExposures = cmdKeys['nExposures'].values[0] if 'nExposures' in cmdKeys else 2
        cableBLampOn = iicActor.actorConfig['fps']['cableBLampOn']

        return cls(exptime, nExposures, cableBLampOn, **seqKeys)

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

    def __init__(self, exptime, cnt, cableBLampOn, **seqKeys):
        FpsSequence.__init__(self, doTurnOnIlluminator=True, cableBLampOn=cableBLampOn, **seqKeys)

        timeLim = 30 + (15 + exptime) * cnt
        self.add('fps', 'testLoop', parseVisit=True, exptime=exptime, cnt=cnt, timeLim=timeLim)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct FpsLoop object."""
        seqKeys = translate.seqKeys(cmdKeys)

        exptime = cmdKeys['exptime'].values[0] if 'exptime' in cmdKeys else 1.0
        cnt = cmdKeys['cnt'].values[0] if 'cnt' in cmdKeys else 1
        cableBLampOn = iicActor.actorConfig['fps']['cableBLampOn']

        return cls(exptime, cnt, cableBLampOn, **seqKeys)


class MoveToPfsDesign(FpsSequence):
    """ fps MoveToPfsDesign command. """
    seqtype = 'moveToPfsDesign'

    def __init__(self, designId, nIteration, tolerance, exptime, maskFile, goHome, twoStepsOff, shortExpOff, noTweak,
                 cableBLampOn, **seqKeys):
        FpsSequence.__init__(self, doTurnOnIlluminator=True, cableBLampOn=cableBLampOn, **seqKeys)

        # Removing maskFile for now, it's broken on fps side (per INSTRM-2192)
        maskFile = False

        # move to pfsDesign.
        self.add('fps', 'moveToPfsDesign', parseVisit=True, designId=designId, iteration=nIteration,
                 tolerance=tolerance, maskFile=maskFile, exptime=exptime, goHome=goHome, twoStepsOff=twoStepsOff,
                 shortExpOff=shortExpOff, noTweak=noTweak, timeLim=600)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys, designId):
        seqKeys = translate.seqKeys(cmdKeys)
        exptime = translate.mcsExposureKeys(cmdKeys, iicActor.actorConfig)
        maskFile = translate.getMaskFilePathFromCmd(cmdKeys, iicActor.actorConfig)

        nIteration = cmdKeys['nIteration'].values[0] if 'nIteration' in cmdKeys else False
        tolerance = cmdKeys['tolerance'].values[0] if 'tolerance' in cmdKeys else False
        goHome = 'noHome' not in cmdKeys
        twoStepsOff = 'twoStepsOff' in cmdKeys
        shortExpOff = 'shortExpOff' in cmdKeys
        noTweak = 'noTweak' in cmdKeys
        cableBLampOn = iicActor.actorConfig['fps']['cableBLampOn']

        return cls(designId, nIteration, tolerance, exptime, maskFile, goHome, twoStepsOff, shortExpOff, noTweak,
                   cableBLampOn, **seqKeys)


class MoveToHome(FpsSequence):
    """ fps MoveToHome command."""
    seqtype = 'moveToHome'

    def __init__(self, exptime, designId, cableBLampOn, thetaCCW=False, noMCSexposure=False, **seqKeys):
        FpsSequence.__init__(self, doTurnOnIlluminator=not noMCSexposure, cableBLampOn=cableBLampOn, **seqKeys)

        # move cobras to home, not supposed to, but meh.
        self.add('fps', 'moveToHome all',
                 parseVisit=not noMCSexposure, exptime=exptime, designId=designId,
                 thetaCCW=thetaCCW, noMCSexposure=noMCSexposure,
                 timeLim=120)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys, designId):
        seqKeys = translate.seqKeys(cmdKeys)
        exptime = translate.mcsExposureKeys(cmdKeys, iicActor.actorConfig)
        cableBLampOn = iicActor.actorConfig['fps']['cableBLampOn']
        thetaCCW = 'thetaCCW' in cmdKeys
        noMCSexposure = 'noMCSexposure' in cmdKeys

        return cls(exptime, designId, cableBLampOn, thetaCCW, noMCSexposure, **seqKeys)


class GenPfsConfigFromMcs(FpsSequence):
    """ fps MoveToPfsDesign command. """
    seqtype = 'genPfsConfigFromMcs'

    def __init__(self, exptime, designId, cableBLampOn, **seqKeys):
        FpsSequence.__init__(self, doTurnOnIlluminator=True, cableBLampOn=cableBLampOn, **seqKeys)

        self.add('mcs', 'expose object', exptime=exptime, parseFrameId=True, doFibreId=True)
        self.add('fps', 'genPfsConfigFromMcs', parseVisit=True, designId=designId)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys, designId):
        """Defining rules to construct DotCrossing object."""
        seqKeys = translate.seqKeys(cmdKeys)
        exptime = translate.mcsExposureKeys(cmdKeys, iicActor.actorConfig)
        cableBLampOn = iicActor.actorConfig['fps']['cableBLampOn']

        return cls(exptime, designId, cableBLampOn, **seqKeys)


class GenBlackDotsConfig(GenPfsConfigFromMcs):
    seqtype = 'genBlackDotsPfsConfig'


class CobraMoveAngles(FpsSequence):
    """ fps MotorOntimeSearch command. """
    seqtype = 'cobraMoveAngles'

    def __init__(self, phi, theta, angle, maskFile, genPfsConfig, exptime, designId, cableBLampOn, **seqKeys):
        FpsSequence.__init__(self, **seqKeys, doTurnOnIlluminator=genPfsConfig, cableBLampOn=cableBLampOn)

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
        exptime = translate.mcsExposureKeys(cmdKeys, iicActor.actorConfig)
        cableBLampOn = genPfsConfig and iicActor.actorConfig['fps']['cableBLampOn']

        return cls(phi, theta, angle, maskFile, genPfsConfig, exptime, designId, cableBLampOn, **seqKeys)


class CobraMoveSteps(FpsSequence):
    """ fps MotorOntimeSearch command. """
    seqtype = 'cobraMoveSteps'

    def __init__(self, phi, theta, stepSize, maskFile, genPfsConfig, exptime, designId, cableBLampOn, **seqKeys):
        FpsSequence.__init__(self, **seqKeys, doTurnOnIlluminator=genPfsConfig, cableBLampOn=cableBLampOn)

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
        exptime = translate.mcsExposureKeys(cmdKeys, iicActor.actorConfig)
        cableBLampOn = genPfsConfig and iicActor.actorConfig['fps']['cableBLampOn']

        return cls(phi, theta, stepSize, maskFile, genPfsConfig, exptime, designId, cableBLampOn, **seqKeys)


class MovePhiToAngle(FpsSequence):
    """ fps MovePhiToAngle command. """
    seqtype = 'movePhiToAngle'
    timePerIteration = 150

    def __init__(self, angle, nIteration, **seqKeys):
        FpsSequence.__init__(self, **seqKeys)
        timeLim = nIteration * MovePhiToAngle.timePerIteration

        self.add('fps', 'movePhiToAngle', parseVisit=True, angle=angle, iteration=nIteration, timeLim=timeLim)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct FpsLoop object."""
        seqKeys = translate.seqKeys(cmdKeys)

        angle = cmdKeys['angle'].values[0]
        nIteration = cmdKeys['nIteration'].values[0]

        return cls(angle, nIteration, **seqKeys)


class MoveToSafePosition(FpsSequence):
    """ fps MoveToSafePosition command. """
    seqtype = 'moveToSafePosition'

    def __init__(self, **seqKeys):
        FpsSequence.__init__(self, **seqKeys)

        self.add('fps', 'moveToSafePosition', parseVisit=True, timeLim=600)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct FpsLoop object."""
        seqKeys = translate.seqKeys(cmdKeys)
        return cls(**seqKeys)


class GotoVerticalFromPhi60(FpsSequence):
    """ fps GotoVerticalFromPhi60 command. """
    seqtype = 'gotoVerticalFromPhi60'

    def __init__(self, **seqKeys):
        FpsSequence.__init__(self, **seqKeys)

        self.add('fps', 'moveToSafePosition', parseVisit=True, timeLim=600)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct FpsLoop object."""
        seqKeys = translate.seqKeys(cmdKeys)
        return cls(**seqKeys)


class MakeMotorMap(FpsSequence):
    """ fps MakeMotorMap command. """
    seqtype = 'makeMotorMap'
    timePerRepeat = 150

    def __init__(self, phi, theta, stepsize, repeat, slowOnly, **seqKeys):
        FpsSequence.__init__(self, **seqKeys)
        timeLim = repeat * MakeMotorMap.timePerRepeat

        self.add('fps', 'makeMotorMap', parseVisit=True,
                 phi=phi, theta=theta, stepsize=stepsize, repeat=repeat, slowOnly=slowOnly, timeLim=timeLim)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct FpsLoop object."""
        seqKeys = translate.seqKeys(cmdKeys)

        phi = 'phi' in cmdKeys
        theta = 'theta' in cmdKeys
        stepsize = cmdKeys['stepsize'].values[0]
        repeat = cmdKeys['repeat'].values[0]
        slowOnly = 'slowOnly' in cmdKeys

        return cls(phi, theta, stepsize, repeat, slowOnly, **seqKeys)


class MakeOntimeMap(FpsSequence):
    """ fps MakeOntimeMap command. """
    seqtype = 'makeOntimeMap'

    def __init__(self, phi, theta, **seqKeys):
        FpsSequence.__init__(self, **seqKeys)

        self.add('fps', 'makeOntimeMap', parseVisit=True, phi=phi, theta=theta, timeLim=600)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct FpsLoop object."""
        seqKeys = translate.seqKeys(cmdKeys)

        phi = 'phi' in cmdKeys
        theta = 'theta' in cmdKeys

        return cls(phi, theta, **seqKeys)


class AngleConvergenceTest(FpsSequence):
    """ fps AngleConvergenceTest command. """
    seqtype = 'angleConvergenceTest'

    def __init__(self, phi, theta, angleTargets, **seqKeys):
        FpsSequence.__init__(self, **seqKeys)

        self.add('fps', 'angleConvergenceTest', parseVisit=True,
                 phi=phi, theta=theta, angleTargets=angleTargets, timeLim=600)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct FpsLoop object."""
        seqKeys = translate.seqKeys(cmdKeys)

        phi = 'phi' in cmdKeys
        theta = 'theta' in cmdKeys
        angleTargets = cmdKeys['angleTargets'].values[0]

        return cls(phi, theta, angleTargets, **seqKeys)


class TargetConvergenceTest(FpsSequence):
    """ fps TargetConvergenceTest command. """
    seqtype = 'targetConvergenceTest'

    def __init__(self, ontime, speed, totalTargets, maxsteps, **seqKeys):
        FpsSequence.__init__(self, **seqKeys)
        timeLim = int(TargetConvergenceTest.timeLim / speed)

        self.add('fps', 'targetConvergenceTest', parseVisit=True,
                 ontime=ontime, speed=speed, totalTargets=totalTargets, maxsteps=maxsteps, timeLim=timeLim)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct FpsLoop object."""
        seqKeys = translate.seqKeys(cmdKeys)

        ontime = 'ontime' in cmdKeys
        speed = 'speed' in cmdKeys
        totalTargets = cmdKeys['totalTargets'].values[0]
        maxsteps = cmdKeys['maxsteps'].values[0]

        return cls(ontime, speed, totalTargets, maxsteps, **seqKeys)


class MotorOntimeSearch(FpsSequence):
    """ fps MotorOntimeSearch command. """
    seqtype = 'motorOntimeSearch'

    def __init__(self, phi, theta, **seqKeys):
        FpsSequence.__init__(self, **seqKeys)

        self.add('fps', 'motorOntimeSearch', parseVisit=True, phi=phi, theta=theta, timeLim=600)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct FpsLoop object."""
        seqKeys = translate.seqKeys(cmdKeys)

        phi = 'phi' in cmdKeys
        theta = 'theta' in cmdKeys

        return cls(phi, theta, **seqKeys)
