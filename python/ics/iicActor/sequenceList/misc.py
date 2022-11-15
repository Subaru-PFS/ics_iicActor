import os

import iicActor.utils.translate as translate
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
        self.add(actor='sps', cmdStr='bia on')
        self.add(actor='peb', cmdStr='led on')

        self.add(actor='mcs', cmdStr='expose object', parseFrameId=True, exptime=exptime, doFibreId=True)

        for iterNum in range(count):
            self.add(actor='fps', cmdStr=f'cobraMoveSteps {self.motor}', stepsize=stepSize)
            self.add(actor='mcs', cmdStr='expose object', parseFrameId=True, exptime=exptime, doFibreId=True)

        # turning off the illuminators
        self.tail.add(actor='sps', cmdStr='bia off')
        self.tail.add(actor='peb', cmdStr='led off')

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
            self.add(actor='fps', cmdStr=f'cobraMoveSteps phi', stepsize=3000,
                     maskFile=os.path.join(maskFilesRoot, f'group{groupId}.csv'))
            # use sps erase command to niet things up.
            self.add(actor='sps', cmdStr='erase', cams=cams)
            self.expose('domeflat', exptime, cams, windowKeys=windowKeys)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        seqKeys = translate.seqKeys(cmdKeys)
        identKeys = translate.identKeys(cmdKeys)
        # we are using hsc ring lamps.
        windowedFlatConfig = iicActor.actorConfig['windowedFlat']['hscLamps']
        exptime = windowedFlatConfig.pop('exptime')
        # group 25 does not exist.
        fiberGroups = cmdKeys['fiberGroups'].values if 'fiberGroups' in cmdKeys else list(set(range(2, 32)) - {25})
        maskFilesRoot = iicActor.actorConfig['maskFiles']['rootDir']

        cams = iicActor.engine.resourceManager.spsConfig.identify(**identKeys)

        return cls(cams, exptime, windowedFlatConfig, maskFilesRoot, fiberGroups, **seqKeys)
