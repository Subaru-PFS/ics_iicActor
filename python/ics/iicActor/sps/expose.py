import logging

import ics.iicActor.utils.opdb as opdbUtils
import ics.utils.cmd as cmdUtils
import ics.utils.sps.fits as fits
import numpy as np
import pfs.utils.pfsConfigUtils as pfsConfigUtils
import pfscore.gen2 as gen2
from ics.iicActor.utils.pfsConfig.illumination import updateFiberStatus
from ics.iicActor.utils.subcmd import CmdRet
from ics.iicActor.utils.visited import VisitedCmd
from ics.utils.fits import mhs as fitsMhs
from iicActor.utils import exception
from opscore.utility.qstr import qstr
from pfs.datamodel import PfsConfig, InstrumentStatusFlag


class SpsExpose(VisitedCmd):
    """Handle SPS exposure command specifics, including visit and pfsConfig management."""

    def __init__(self, *args, **kwargs):
        # Always parse visit information
        super().__init__(*args, parseVisit=True, **kwargs)

        self.visit = None
        self.pfsConfig = None
        self.doWritePfsConfig = True

        # Extract exposure type from command string
        _, exptype, _ = self.cmdStr.split(' ', 2)
        self.exptype = exptype.strip()

        self.logger = logging.getLogger('spsExpose')

    @property
    def visitId(self):
        """Return visit ID or -1 if no visit is defined."""
        return -1 if self.visit is None else self.visit.visitId

    @property
    def cmdStrAndVisit(self):
        """Combine command string with visit and metadata."""
        allArgs = [self.cmdStr, f'{self.visitCmdArg}={self.visitId}']

        if self.pfsConfig is not None:
            allArgs.append(self.getMetadata())

        return ' '.join(allArgs).strip()

    @classmethod
    def specify(cls, sequence, exptype, exptime, cams, timeOffset=180, **kwargs):
        """Specify exposure command with timing limits."""
        timeLim = timeOffset + exptime
        exptime = exptime if exptime else None
        return cls(sequence, 'sps', f'expose {exptype}', exptime=exptime, cams=cams, timeLim=timeLim, **kwargs)

    def getMetadata(self):
        """Format metadata argument."""
        designInfo = [f'0x{self.pfsConfig.pfsDesignId:016x}', qstr(self.pfsConfig.designName)]
        ids = list(map(str, [self.pfsConfig.visit0, self.sequence.sequence_id, self.sequence.parseGroupId()]))
        metadata = designInfo + ids
        return f'metadata={",".join(metadata)}'

    def call(self, cmd):
        """Execute command with visit and return CmdRet object."""
        try:
            cmdRet = self.getVisitedCall(cmd)
        except gen2.FetchVisitFromGen2 as e:
            lastReply = str(e)
            cmdRet = CmdRet(1, [lastReply], lastReply)  # converting to a consistent output.

        return cmdRet

    def getVisitedCall(self, cmd):
        """Set visit, process command, and finalize by inserting into visit_set."""
        with self.visitManager.getVisit(caller='sps') as visit:
            self.prepareVisit(visit)
            cmdRet = super().call(cmd)

            # Insert into visit_set in the database
            opdbUtils.insertVisitSet('sps', sequence_id=self.sequence.sequence_id, pfs_visit_id=self.visitId)

            # Write pfsConfig if required, should not happen but let's be careful.
            if self.doWritePfsConfig:
                self.writePfsConfig(self.pfsConfig)

            # Release the visit as it is no longer active
            self.release()

        return cmdRet

    def prepareVisit(self, visit):
        """Prepare visit by setting it, generating keys, and verifying configuration."""
        self.visit = visit
        self.genKeys(self.sequence.getCmd())

        # Manage lightSources for different exposure types
        if not self.visitManager.activeField:
            raise RuntimeError('No active pfsDesign is declared!')

        # Bump up ag visit whenever sps is taking object.
        if self.sequence.isPfiExposure and self.exptype == 'object':
            self.iicActor.cmdr.call(actor='ag', cmdStr=f'autoguide reconfigure visit={self.visitId}', timeLim=10)

        # Compute the change in INSROT since convergence.
        dINSROT = self.getDeltaINSROT()

        # Obtain and register pfsConfig
        self.pfsConfig = self.makePfsConfig(dINSROT=dINSROT)
        self.register()

    def getDeltaINSROT(self):
        """Compute the change in INSROT (instrument rotation) between the visit0 and the current visit."""
        # Only compute if the sequence is a PFI exposure
        if not self.sequence.isPfiExposure:
            return None

        try:
            # Retrieve the reference visit (visit0) for comparison
            visit0 = self.visitManager.activeField.getVisit0()
            # Compute the delta INSROT between now and visit0.
            dINSROT = opdbUtils.getDeltaINSROT(visit0, self.visitId)
        except (ValueError, exception.OpDBFailure):
            # Handle cases where INSROT calculation fails
            dINSROT = float(fitsMhs.INVALID)

        return dINSROT

    def makePfsConfig(self, dINSROT=None):
        """Retrieve or create pfsConfig and ensure matching arms in sequence."""
        cards = fits.getPfsConfigCards(self.iicActor, self.sequence.getCmd(), self.visitId, expType=self.exptype)

        # dINSROT is not always relevant, for example if PFS is not on the telescope.
        if dINSROT is not None:
            cards.update({'W_DINROT': (dINSROT, "[deg] INSROT delta between sps visit and convergence.")})

        selectedCams = self.sequence.engine.keyRepo.getSelectedCams(self.sequence.cams)
        camMask = PfsConfig.getCameraMask(selectedCams)

        pfsConfig = self.visitManager.activeField.makePfsConfig(self.visitId, cards=cards, camMask=camMask)

        # setting INSROT_MISMATCH in pfsConfig if dINSROT > threshold
        if dINSROT not in {None, float(fitsMhs.INVALID)} and abs(dINSROT) > self.iicActor.actorConfig['maxDeltaINSROT']:
            pfsConfig.setInstrumentStatusFlag(InstrumentStatusFlag.INSROT_MISMATCH)

        # Insert into opdb immediately
        opdbUtils.insertPfsConfigSps(pfs_visit_id=pfsConfig.visit, visit0=pfsConfig.visit0,
                                     camMask=pfsConfig.camMask, instStatusFlag=pfsConfig.instStatusFlag)

        # Ensure pfsConfig arms match those used in current sequence
        pfsConfig.arms = self.sequence.matchPfsConfigArms(pfsConfig.arms)

        # Reporting that the pfsConfig is a direct copy of the pfsDesign
        isFake = not np.nansum(np.abs(pfsConfig.pfiNominal - pfsConfig.pfiCenter))
        if self.sequence.isPfiExposure and isFake:
            self.sequence.getCmd().warn('text="pfsConfig.pfiCenter was faked from the pfsDesign!"')

        # writing pfsConfig right away since it doesn't need any further update.
        if self.exptype in ['bias', 'dark']:
            self.writePfsConfig(pfsConfig)

        return pfsConfig

    def updateFiberIllumination(self, status):
        """Update fiber illumination status based on configuration settings."""
        pfsConfigKnobs = self.iicActor.actorConfig['pfsConfig']
        updateFiberStatus(
            self.pfsConfig,
            fiberIlluminationStatus=status,
            doUpdateEngineeringFiberStatus=pfsConfigKnobs['doUpdateEngineeringFiberStatus'],
            doUpdateScienceFiberStatus=pfsConfigKnobs['doUpdateScienceFiberStatus']
        )
        self.writePfsConfig(self.pfsConfig)

    def writePfsConfig(self, pfsConfig):
        """Write pfsConfig to disk and track with pfsConfig key."""
        if not self.doWritePfsConfig or pfsConfig is None:
            return

        # Save pfsConfig to disk
        pfsConfigUtils.writePfsConfig(pfsConfig)
        self.iicActor.genPfsConfigKey(self.sequence.getCmd(), pfsConfig)
        self.doWritePfsConfig = False  # Prevent redundant writes

    def register(self):
        """Register current visit as active."""
        self.logger.info(f'Registering {self.visit.visitId:06d} : 0x{id(self):016x} in active visits.')
        self.visitManager.activeVisit[self.visitId] = self

    def release(self):
        """Release current visit from active list."""
        self.logger.info(f'Releasing {self.visit.visitId:06d} : 0x{id(self):016x} from active visits.')
        self.visitManager.activeVisit.pop(self.visitId, None)

    def abort(self, cmd):
        """Abort current exposure if visit is valid."""
        if self.visitId == -1:
            return

        cmdVar = self.iicActor.cmdr.call(actor='sps',
                                         cmdStr=f'exposure abort visit={self.visitId}',
                                         forUserCmd=cmd,
                                         timeLim=10)
        if cmdVar.didFail:
            cmd.warn(cmdUtils.formatLastReply(cmdVar))

    def finishNow(self, cmd):
        """Finish current exposure if visit is valid."""
        if self.visitId == -1:
            return

        cmdVar = self.iicActor.cmdr.call(actor='sps',
                                         cmdStr=f'exposure finish visit={self.visitId}',
                                         forUserCmd=cmd,
                                         timeLim=10)
        if cmdVar.didFail:
            cmd.warn(cmdUtils.formatLastReply(cmdVar))
