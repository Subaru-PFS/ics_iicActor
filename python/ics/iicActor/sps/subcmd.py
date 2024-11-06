import logging

import ics.iicActor.utils.opdb as opdbUtils
import ics.utils.cmd as cmdUtils
import ics.utils.sps.fits as fits
import numpy as np
import pfs.utils.pfsConfigUtils as pfsConfigUtils
import pfscore.gen2 as gen2
from ics.iicActor.utils.pfsConfig.illumination import updateFiberStatus
from ics.iicActor.utils.subcmd import SubCmd, CmdRet
from ics.iicActor.utils.visited import VisitedCmd
from opscore.utility.qstr import qstr


class GetVisitFailed(CmdRet):
    def __init__(self, lastReply):
        CmdRet.__init__(self, 1, [lastReply], lastReply)


class SpsExpose(VisitedCmd):
    """ Placeholder to handle sps expose command specificities"""

    def __init__(self, *args, **kwargs):
        # always parse visit
        VisitedCmd.__init__(self, *args, parseVisit=True, **kwargs)

        self.visit = None
        self.visit0 = None
        self.pfsConfig = None
        self.doWritePfsConfig = True

        __, exptype, __ = self.cmdStr.split(' ', 2)
        self.exptype = exptype.strip()

        self.logger = logging.getLogger('spsExpose')

    @property
    def visitId(self):
        visitId = -1 if self.visit is None else self.visit.visitId
        return visitId

    @property
    def cmdStrAndVisit(self):
        """Parse visit and metadata"""
        allArgs = [self.cmdStr, f'{self.visitCmdArg}={self.visitId}']

        if self.pfsConfig is not None:
            allArgs.append(self.getMetadata())

        return ' '.join(allArgs).strip()

    def getMetadata(self):
        """"""
        designInfo = [f'0x{self.pfsConfig.pfsDesignId:016x}', qstr(self.pfsConfig.designName)]
        ids = list(map(str, [self.visit0, self.sequence.sequence_id, self.sequence.parseGroupId()]))
        metadata = designInfo + ids

        return f'metadata={",".join(metadata)}'

    @classmethod
    def specify(cls, sequence, exptype, exptime, cams, timeOffset=180, **kwargs):
        timeLim = timeOffset + exptime
        exptime = exptime if exptime else None
        return cls(sequence, 'sps', f'expose {exptype}', exptime=exptime, cams=cams, timeLim=timeLim, **kwargs)

    def call(self, cmd):
        """getVisitedCall get the visit and parse it, but SubCmd.call() must always return a CmdRet object."""
        try:
            cmdRet = self.getVisitedCall(cmd)
        except gen2.FetchVisitFromGen2 as e:
            cmdRet = GetVisitFailed(str(e))

        return cmdRet

    def getVisitedCall(self, cmd):
        """Get and attach your visit, then parse it, insert into visit_set to finish."""
        with self.visitManager.getVisit(caller='sps') as visit:
            # set new visit
            self.prepareVisit(visit)
            # regular visitedCall which will parse the fresh new visit.
            cmdRet = VisitedCmd.call(self, cmd)

            # insert into visit_set
            opdbUtils.insertVisitSet('sps', sequence_id=self.sequence.sequence_id, pfs_visit_id=self.visitId)

            if self.doWritePfsConfig:  # should not be the case but still being careful.
                self.writePfsConfig(self.pfsConfig)

            # no longer an active visit.
            self.release()

        return cmdRet

    def prepareVisit(self, visit):
        """Set the visit and generate keys."""
        self.visit = visit
        self.genKeys(self.sequence.cmd)

        # lightSources can be a bit tricky, sequence member is actually set to None for biases and darks.
        # For those it's possible to have multiple lightSources, not sure what to do in that case.
        # Since you could have multiple designId for a given visit, and we don't support merging.
        # It does not probably matter in any case for biases and darks.

        if not self.visitManager.activeField:
            raise RuntimeError('No pfsDesign declared as current !')

        if self.sequence.isPfiExposure and self.exptype == 'object':
            # Bump up ag visit whenever sps is taking object.
            self.iicActor.cmdr.call(actor='ag', cmdStr=f'autoguide reconfigure visit={self.visitId}', timeLim=10)

        # handling pfsConfig
        self.pfsConfig, self.visit0 = self.getPfsConfig()

        # registering active visit.
        self.register()

    def getPfsConfig(self):
        # Retrieve additional pfsConfig metadata from FITS headers.
        cards = fits.getPfsConfigCards(self.iicActor, self.sequence.cmd, self.visitId,
                                       expType=self.exptype)

        # Create or retrieve the pfsConfig object for the current visit.
        pfsConfig, visit0 = self.visitManager.activeField.getPfsConfig(self.visitId, cards=cards)

        # inserting in opdb immediately.
        opdbUtils.insertPfsConfigSps(pfs_visit_id=pfsConfig.visit, visit0=visit0)

        # Ensure that pfsConfig arms match the arms used in the current sequence.
        pfsConfig.arms = self.sequence.matchPfsConfigArms(pfsConfig.arms)

        # checking that pfsConfig is a straigh copy of the pfsDesign.
        isFake = not np.nansum(np.abs(pfsConfig.pfiNominal - pfsConfig.pfiCenter))

        if self.sequence.isPfiExposure and isFake:
            self.sequence.cmd.warn('text="pfsConfig.pfiCenter was faked from the pfsDesign !"')

        # writing pfsConfig right away since it doesn't need any further update.
        if self.exptype in ['bias', 'dark']:
            self.writePfsConfig(pfsConfig)

        return pfsConfig, visit0

    def updateFiberIllumination(self, status):
        pfsConfigKnobs = self.iicActor.actorConfig['pfsConfig']
        updateFiberStatus(self.pfsConfig, fiberIlluminationStatus=status,
                          doUpdateEngineeringFiberStatus=pfsConfigKnobs['doUpdateEngineeringFiberStatus'],
                          doUpdateScienceFiberStatus=pfsConfigKnobs['doUpdateScienceFiberStatus'])
        self.writePfsConfig(self.pfsConfig)

    def writePfsConfig(self, pfsConfig):
        """Wrapper around pfsConfig.write() method."""
        if not self.doWritePfsConfig or pfsConfig is None:
            return

        # writing pfsConfig to disk.
        pfsConfigUtils.writePfsConfig(pfsConfig)

        # Generate and log the pfsConfig key for tracking in the IIC actor.
        self.iicActor.genPfsConfigKey(self.sequence.cmd, pfsConfig)

        # not writing in the future.
        self.doWritePfsConfig = False

    def register(self):
        # adding to the active visit
        self.logger.info(f'Registering {self.visit.visitId:06d} : 0x{id(self):016x} in active visits.')
        self.visitManager.activeVisit[self.visitId] = self

    def release(self):
        self.logger.info(f'Releasing {self.visit.visitId:06d} : 0x{id(self):016x} from active visits.')
        self.visitManager.activeVisit.pop(self.visitId, None)

    def abort(self, cmd):
        """ Abort current exposure """
        if self.visitId == -1:
            return

        cmdVar = self.iicActor.cmdr.call(actor='sps',
                                         cmdStr=f'exposure abort visit={self.visitId}',
                                         forUserCmd=cmd,
                                         timeLim=10)
        if cmdVar.didFail:
            cmd.warn(cmdUtils.formatLastReply(cmdVar))

    def finishNow(self, cmd):
        """ Finish current exposure """
        if self.visitId == -1:
            return

        cmdVar = self.iicActor.cmdr.call(actor='sps',
                                         cmdStr=f'exposure finish visit={self.visitId}',
                                         forUserCmd=cmd,
                                         timeLim=10)
        if cmdVar.didFail:
            cmd.warn(cmdUtils.formatLastReply(cmdVar))


class LampsCmd(SubCmd):
    """ Placeholder to handle lamps command specificities"""

    def __init__(self, sequence, actor, *args, **kwargs):
        if not sequence.lightSource.lampsActor:
            raise RuntimeError(f'cannot control lampActor for lightSource={sequence.lightSource} !')

        SubCmd.__init__(self, sequence, sequence.lightSource.lampsActor, *args, **kwargs)

    def abort(self, cmd):
        """ Abort warmup """
        cmdVar = self.iicActor.cmdr.call(actor=self.actor,
                                         cmdStr='abort',
                                         forUserCmd=cmd,
                                         timeLim=10)
        if cmdVar.didFail:
            cmd.warn(cmdUtils.formatLastReply(cmdVar))
            # raise RuntimeError("Failed to abort exposure")


class DcbCmd(LampsCmd):
    def __init__(self, sequence, *args, **kwargs):
        if not sequence.lightSource.useDcbActor:
            raise RuntimeError('this command has been designed for dcb only')

        LampsCmd.__init__(self, sequence, *args, **kwargs)
