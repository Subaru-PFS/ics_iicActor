import os

import iicActor.utils.translate as translate
from ics.iicActor.sequenceList.fps import MoveToPfsDesign, FpsSequence
from ics.iicActor.sps.sequence import SpsSequence
from ics.iicActor.sps.timedLamps import TimedLampsSequence


class NearDotConvergence(MoveToPfsDesign):
    seqtype = 'nearDotConvergence'

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys, designId):
        """Defining rules to construct NearDotConvergence object."""
        seqKeys = translate.seqKeys(cmdKeys)
        exptime = translate.mcsExposureKeys(cmdKeys, iicActor.actorConfig)
        config = iicActor.actorConfig['nearDotConvergence'].copy()
        config.update(exptime=exptime)

        if 'maskFile' in cmdKeys:
            maskFile = cmdKeys['maskFile'].values[0]
            maskFile = os.path.join(iicActor.actorConfig['maskFiles']['rootDir'], f'{maskFile}.csv')
        else:
            maskFile = False

        return cls(designId, maskFile=maskFile, goHome=True, noTweak=True, twoStepsOff=False, **config, **seqKeys)


class DotCrossing(FpsSequence):
    """ fps MoveToPfsDesign command. """
    seqtype = 'dotCrossing'

    def __init__(self, stepSize, count, exptime, **seqKeys):
        FpsSequence.__init__(self, **seqKeys)

        # turning illuminators on
        self.add('sps', 'bia on')
        self.add('peb', 'led on')
        self.add('dcb', 'power on cableB')

        self.add('mcs', 'expose object', parseFrameId=True, exptime=exptime, doFibreId=True)

        for iterNum in range(count):
            self.add('fps', f'cobraMoveSteps {self.motor}', stepsize=stepSize)
            self.add('mcs', 'expose object', parseFrameId=True, exptime=exptime, doFibreId=True)

        # turning illuminators off
        self.tail.add('sps', 'bia off')
        self.tail.add('peb', 'led off')
        self.tail.add('dcb', 'power off cableB')

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct DotCrossing object."""
        seqKeys = translate.seqKeys(cmdKeys)
        exptime = translate.mcsExposureKeys(cmdKeys, iicActor.actorConfig)
        config = iicActor.actorConfig['dotCrossing'].copy()
        config.update(exptime=exptime)
        # updating config with optional args
        for arg in [optArg for optArg in ['stepSize', 'count'] if optArg in cmdKeys]:
            config[arg] = cmdKeys[arg].values[0]

        return cls(**config, **seqKeys)


class PhiCrossing(DotCrossing):
    motor = 'phi'
    seqtype = 'phiCrossing'


class ThetaCrossing(DotCrossing):
    motor = 'theta'
    seqtype = 'thetaCrossing'


class FiberIdentification(SpsSequence):
    """ fps MoveToPfsDesign command. """
    seqtype = 'fiberIdentification'

    def __init__(self, cams, exptime, windowKeys, maskFilesRoot, fiberGroups, **seqKeys):
        SpsSequence.__init__(self, cams, **seqKeys)

        self.expose('domeflat', exptime, cams, windowKeys=windowKeys)

        for groupId in fiberGroups:
            self.add('fps', f'cobraMoveSteps phi',
                     stepsize=3000, maskFile=os.path.join(maskFilesRoot, f'mtpGroup{str(groupId).zfill(2)}.csv'))
            # use sps erase command to niet things up.
            self.add('sps', 'erase', cams=cams)
            self.expose('domeflat', exptime, cams, windowKeys=windowKeys)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        cams = iicActor.spsConfig.keysToCam(cmdKeys)
        seqKeys = translate.seqKeys(cmdKeys)
        # we are using hsc ring lamps.
        windowedFlatConfig = iicActor.actorConfig['windowedFlat']['hscLamps'].copy()
        exptime = windowedFlatConfig.pop('exptime')
        # group 25 does not exist.
        default = list(set(range(2, 32)) - {25})
        fiberGroups = cmdKeys['fiberGroups'].values if 'fiberGroups' in cmdKeys else default
        maskFilesRoot = iicActor.actorConfig['maskFiles']['rootDir']

        return cls(cams, exptime, windowedFlatConfig, maskFilesRoot, fiberGroups, **seqKeys)


class DotRoach(SpsSequence):
    """ fps MoveToPfsDesign command. """
    seqtype = 'dotRoach'
    useLamps = 'hscLamps'

    @staticmethod
    def calculateSteps(mode='safe'):
        # x = np.arange(nSteps)
        # a = -shapeF / minStepIter
        # Y = 1 / 2 * a * x ** 2 + shapeF * x + step0
        # return np.ceil(Y).astype('int')
        # steps1 = DotRoach.calculateSteps(step0=116, minStepIter=5, nSteps=16, shapeF=-30)
        # steps2 = DotRoach.calculateSteps(step0=30, minStepIter=1, nSteps=5, shapeF=-10)

        #  vanilla values from iic_sequence_id 19106.
        steps11 = [116, 89, 68, 53, 44, 41, 44, 53, 68, 89, 116, 149, 188, 233, 284, 341]
        steps12 = [25, 35, 45, 55, 65, 75]

        # safer scenario.
        # steps21 = [125, 95, 75, 60, 50, 45, 50, 60, 75, 95, 125, 160, 200, 245, 300, 360]
        # steps22 = [25, 32, 40, 50, 60, 70, 80]

        # safer scenario, adding extra steps
        # steps21 = [141, 107, 84, 67, 56, 50, 56, 67, 84, 107, 141, 180, 248, 316, 372, 429, 485]
        # steps22 = [25, 32, 40, 50, 60, 70, 80, 90]

        # safer scenario, adding extra steps
        steps21 = [141, 107, 84, 67, 56, 50, 56, 67, 84, 107, 141, 180, 240, 310, 390, 490, 610]
        steps22 = [25, 32, 40, 50, 60, 70, 80, 90]

        # quicker scenario.
        steps31 = [177, 133, 100, 76, 63, 62, 77, 102, 140, 192, 265, 362, 494]
        steps32 = [30, 42, 56, 74, 100]

        if mode == 'first':
            return steps11, steps12
        elif mode == 'safe':
            return steps21, steps22
        elif mode == 'fast':
            return steps31, steps32
        else:
            raise ValueError(f'unknown mode : {mode}')

    def __init__(self, cams, exptime, windowKeys, maskFile, keepMoving, mode, rootDir, stepSize, count, motor,
                 **seqKeys):
        SpsSequence.__init__(self, cams, **seqKeys)

        dataRoot = os.path.join(rootDir, 'current')
        maskFilesRoot = os.path.join(dataRoot, 'maskFiles')

        def maskFilePath(iterNum):
            return os.path.join(maskFilesRoot, f'iter{iterNum}.csv')

        steps1, steps2 = DotRoach.calculateSteps(mode=mode)

        # use sps erase command to niet things up.
        self.add('sps', 'erase', cams=cams)

        # first exposure after going to nearDot
        maskNumOffset = 1
        self.expose('domeflat', exptime, cams, windowKeys=windowKeys)
        self.add('drp', 'processDotRoach', iteration=maskNumOffset)

        for iterNum, stepSize in enumerate(steps1):
            maskFileNum = maskNumOffset + iterNum
            self.add('fps', f'cobraMoveSteps {motor}', stepsize=-stepSize, maskFile=maskFilePath(maskFileNum))

            # for the last iter, we declare that'll go reverse.
            if iterNum == len(steps1) - 1:
                self.add('drp', 'dotRoach phase2')

            # expose and process.
            self.expose('domeflat', exptime, cams, windowKeys=windowKeys)
            self.add('drp', 'processDotRoach', iteration=maskFileNum + 1)

        maskNumOffset += len(steps1)
        for iterNum, stepSize in enumerate(steps2):
            maskFileNum = iterNum + maskNumOffset
            self.add('fps', f'cobraMoveSteps {motor}', stepsize=stepSize, maskFile=maskFilePath(maskFileNum))

            # no need to go further
            if iterNum == len(steps2) - 1:
                break

            # expose and process.
            self.expose('domeflat', exptime, cams, windowKeys=windowKeys)
            self.add('drp', 'processDotRoach', iteration=maskFileNum + 1)

        # turning drp processing off
        self.add('drp', 'stopDotRoach')

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        cams = iicActor.spsConfig.keysToCam(cmdKeys)
        seqKeys = translate.seqKeys(cmdKeys)

        windowedFlatConfig = iicActor.actorConfig['windowedFlat'][cls.useLamps].copy()
        exptime = windowedFlatConfig.pop('exptime')
        # overriding using user provided exptime.
        exptime = cmdKeys['exptime'].values[0] if 'exptime' in cmdKeys else exptime

        # construct maskFile path.
        maskFile = cmdKeys['maskFile'].values[0] if 'maskFile' in cmdKeys else 'moveAll'
        maskFile = os.path.join(iicActor.actorConfig['maskFiles']['rootDir'], f'{maskFile}.csv')

        # load dotRoach config and override with user parameters.
        config = iicActor.actorConfig['dotRoach'].copy()
        stepSize = cmdKeys['stepSize'].values[0] if 'stepSize' in cmdKeys else config['stepSize']
        count = cmdKeys['count'].values[0] if 'count' in cmdKeys else config['count']
        motor = 'theta' if 'theta' in cmdKeys else config['motor']
        motor = 'phi' if 'phi' in cmdKeys else motor
        config.update(stepSize=stepSize, count=count, motor=motor)

        keepMoving = 'keepMoving' in cmdKeys
        mode = cmdKeys['mode'].values[0] if 'mode' in cmdKeys else 'fast'

        return cls(cams, exptime, windowedFlatConfig, maskFile, keepMoving, mode, **config, **seqKeys)


class DotRoachInit(SpsSequence):
    """ fps MoveToPfsDesign command. """
    seqtype = 'dotRoachInit'
    useLamps = 'hscLamps'

    def __init__(self, cams, exptime, windowKeys, maskFile, keepMoving, mode, rootDir, stepSize, count, motor,
                 **seqKeys):
        SpsSequence.__init__(self, cams, **seqKeys)

        dataRoot = os.path.join(rootDir, 'current')

        # turning drp processing on
        self.add('drp', 'startDotRoach', dataRoot=dataRoot, maskFile=maskFile, keepMoving=keepMoving)

        # use sps erase command to niet things up.
        self.add('sps', 'erase', cams=cams)

        # initial exposure
        self.expose('domeflat', exptime, cams, windowKeys=windowKeys)
        self.add('drp', 'processDotRoach', iteration=0)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        cams = iicActor.spsConfig.keysToCam(cmdKeys)
        seqKeys = translate.seqKeys(cmdKeys)

        windowedFlatConfig = iicActor.actorConfig['windowedFlat'][cls.useLamps].copy()
        exptime = windowedFlatConfig.pop('exptime')
        # overriding using user provided exptime.
        exptime = cmdKeys['exptime'].values[0] if 'exptime' in cmdKeys else exptime

        # construct maskFile path.
        maskFile = cmdKeys['maskFile'].values[0] if 'maskFile' in cmdKeys else 'moveAll'
        maskFile = os.path.join(iicActor.actorConfig['maskFiles']['rootDir'], f'{maskFile}.csv')

        # load dotRoach config and override with user parameters.
        config = iicActor.actorConfig['dotRoach'].copy()
        stepSize = cmdKeys['stepSize'].values[0] if 'stepSize' in cmdKeys else config['stepSize']
        count = cmdKeys['count'].values[0] if 'count' in cmdKeys else config['count']
        motor = 'theta' if 'theta' in cmdKeys else config['motor']
        motor = 'phi' if 'phi' in cmdKeys else motor
        config.update(stepSize=stepSize, count=count, motor=motor)

        keepMoving = 'keepMoving' in cmdKeys
        mode = cmdKeys['mode'].values[0] if 'mode' in cmdKeys else 'fast'

        return cls(cams, exptime, windowedFlatConfig, maskFile, keepMoving, mode, **config, **seqKeys)


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
