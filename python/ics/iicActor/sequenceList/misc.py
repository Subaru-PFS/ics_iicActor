import os

import iicActor.utils.translate as translate
import numpy as np
from ics.iicActor.sequenceList.fps import MoveToPfsDesign, FpsSequence
from ics.iicActor.sps.sequence import SpsSequence


class NearDotConvergence(MoveToPfsDesign):
    seqtype = 'nearDotConvergence'

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys, designId, maskFile=False):
        """Defining rules to construct NearDotConvergence object."""
        seqKeys = translate.seqKeys(cmdKeys)
        exptime = translate.mcsExposureKeys(cmdKeys, iicActor.actorConfig)
        config = iicActor.actorConfig['nearDotConvergence']
        config.update(exptime=exptime)

        return cls(designId, maskFile=maskFile, goHome=True, **config, **seqKeys)


class DotCrossing(FpsSequence):
    """ fps MoveToPfsDesign command. """
    seqtype = 'dotCrossing'

    def __init__(self, stepSize, count, exptime, **seqKeys):
        FpsSequence.__init__(self, **seqKeys)

        # turning on the illuminators
        self.add('sps', 'bia on')
        self.add('peb', 'led on')

        self.add('mcs', 'expose object', parseFrameId=True, exptime=exptime, doFibreId=True)

        for iterNum in range(count):
            self.add('fps', f'cobraMoveSteps {self.motor}', stepsize=stepSize)
            self.add('mcs', 'expose object', parseFrameId=True, exptime=exptime, doFibreId=True)

        # turning off the illuminators
        self.tail.add('sps', 'bia off')
        self.tail.add('peb', 'led off')

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct DotCrossing object."""
        seqKeys = translate.seqKeys(cmdKeys)
        exptime = translate.mcsExposureKeys(cmdKeys, iicActor.actorConfig)
        config = iicActor.actorConfig['dotCrossing']
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
                     stepsize=3000, maskFile=os.path.join(maskFilesRoot, f'group{groupId}.csv'))
            # use sps erase command to niet things up.
            self.add('sps', 'erase', cams=cams)
            self.expose('domeflat', exptime, cams, windowKeys=windowKeys)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        seqKeys = translate.seqKeys(cmdKeys)
        identKeys = translate.identKeys(cmdKeys)
        # we are using hsc ring lamps.
        windowedFlatConfig = iicActor.actorConfig['windowedFlat']['hscLamps'].copy()
        exptime = windowedFlatConfig.pop('exptime')
        # group 25 does not exist.
        fiberGroups = cmdKeys['fiberGroups'].values if 'fiberGroups' in cmdKeys else list(set(range(2, 32)) - {25})
        maskFilesRoot = iicActor.actorConfig['maskFiles']['rootDir']

        cams = iicActor.engine.resourceManager.spsConfig.identify(**identKeys)

        return cls(cams, exptime, windowedFlatConfig, maskFilesRoot, fiberGroups, **seqKeys)


class DotRoach(SpsSequence):
    """ fps MoveToPfsDesign command. """
    seqtype = 'dotRoach'

    @staticmethod
    def calculateSteps(shapeF=-8, minStepIter=12, nSteps=30, step0=90):
        x = np.arange(nSteps)
        a = -shapeF / minStepIter
        Y = 1 / 2 * a * x ** 2 + shapeF * x + step0
        return np.ceil(Y).astype('int')

    def __init__(self, cams, exptime, windowKeys, maskFile, keepMoving, rootDir, stepSize, count, motor, **seqKeys):
        SpsSequence.__init__(self, cams, **seqKeys)

        dataRoot = os.path.join(rootDir, 'current')
        maskFilesRoot = os.path.join(dataRoot, 'maskFiles')

        steps1 = DotRoach.calculateSteps(step0=116, minStepIter=5, nSteps=16, shapeF=-30)
        #steps2 = DotRoach.calculateSteps(step0=30, minStepIter=1, nSteps=5, shapeF=-10)
        steps2 = [25, 35, 45, 55, 65, 75]

        # use sps erase command to niet things up.
        self.add('sps', 'erase', cams=cams)
        # turning drp processing on
        self.add('drp', 'startDotRoach', dataRoot=dataRoot, maskFile=maskFile, keepMoving=keepMoving)

        # initial exposure
        self.expose('domeflat', exptime, cams, windowKeys=windowKeys)
        self.add('drp', 'processDotRoach')
        # first image takes longer to process because of fiberTraces
        self.add('sps', 'erase', cams=cams)

        for iterNum, stepSize in enumerate(steps1):
            self.add('fps', f'cobraMoveSteps {motor}',
                     stepsize=-stepSize, maskFile=os.path.join(maskFilesRoot, f'iter{iterNum}.csv'))

            # for the last iter, we declare that'll go reverse.
            if iterNum == len(steps1) - 1:
                self.add('drp', 'reverseDotRoach')

            # expose and process.
            self.expose('domeflat', exptime, cams, windowKeys=windowKeys)
            self.add('drp', 'processDotRoach')

        for iterNum, stepSize in enumerate(steps2):
            self.add('fps', f'cobraMoveSteps {motor}',
                     stepsize=stepSize, maskFile=os.path.join(maskFilesRoot, f'iter{len(steps1)+iterNum}.csv'))

            # for the last iter, we declare that'll go reverse.
            if iterNum == len(steps2) - 1:
                self.add('drp', 'reverseDotRoach')

            # expose and process.
            self.expose('domeflat', exptime, cams, windowKeys=windowKeys)
            self.add('drp', 'processDotRoach')

        self.add('fps', f'cobraMoveSteps {motor}',
                 stepsize=-20, maskFile=os.path.join(maskFilesRoot, f'iter{len(steps1) + len(steps2)}.csv'))

        # turning drp processing off
        self.tail.add('drp', 'stopDotRoach')

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        seqKeys = translate.seqKeys(cmdKeys)
        identKeys = translate.identKeys(cmdKeys)

        # we are using hsc ring lamps.
        windowedFlatConfig = iicActor.actorConfig['windowedFlat']['hscLamps'].copy()
        exptime = windowedFlatConfig.pop('exptime')

        # construct maskFile path.
        maskFile = cmdKeys['maskFile'].values[0] if 'maskFile' in cmdKeys else 'SM13_moveAll'
        maskFile = os.path.join(iicActor.actorConfig['maskFiles']['rootDir'], f'{maskFile}.csv')

        # load dotRoach config and override with user parameters.
        config = iicActor.actorConfig['dotRoach']
        stepSize = cmdKeys['stepSize'].values[0] if 'stepSize' in cmdKeys else config['stepSize']
        count = cmdKeys['count'].values[0] if 'count' in cmdKeys else config['count']
        motor = 'theta' if 'theta' in cmdKeys else config['motor']
        motor = 'phi' if 'phi' in cmdKeys else motor
        config.update(stepSize=stepSize, count=count, motor=motor)

        keepMoving = 'keepMoving' in cmdKeys

        cams = iicActor.engine.resourceManager.spsConfig.identify(**identKeys)

        return cls(cams, exptime, windowedFlatConfig, maskFile, keepMoving, **config, **seqKeys)
