import os.path

import ics.iicActor.utils.opdb as opdbUtils
import ics.utils.cmd as cmdUtils
import pfs.utils.pfsConfigUtils as pfsConfigUtils
import pfscore.gen2 as gen2
from ics.iicActor.utils.subcmd import SubCmd, CmdRet
from ics.iicActor.utils.visited import VisitedCmd


class GetVisitFailed(CmdRet):
    def __init__(self, lastReply):
        CmdRet.__init__(self, 1, [lastReply], lastReply)


class SpsExpose(VisitedCmd):
    """ Placeholder to handle sps expose command specificities"""

    def __init__(self, *args, **kwargs):
        # always parse visit
        VisitedCmd.__init__(self, *args, parseVisit=True, **kwargs)
        self.visit = None

        __, exptype, __ = self.cmdStr.split(' ', 2)
        self.exptype = exptype.strip()

    @property
    def visitId(self):
        visitId = -1 if self.visit is None else self.visit.visitId
        return visitId

    @classmethod
    def specify(cls, sequence, exptype, exptime, cams, timeOffset=90, **kwargs):
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
            self.freshNewVisit(visit)
            # regular visitedCall which will parse the fresh new visit.
            cmdRet = VisitedCmd.call(self, cmd)
            # insert into visit_set
            opdbUtils.insertVisitSet('sps', sequence_id=self.sequence.sequence_id, pfs_visit_id=self.visitId)

        return cmdRet

    def freshNewVisit(self, visit):
        """Set the visit and generate keys."""
        self.visit = visit
        self.genKeys(self.sequence.cmd)

        if self.sequence.lightSource == 'pfi':
            # make sure to create an associated pfsConfig file, if one is available.
            if self.visitManager.activeField and self.visitManager.activeField.pfsConfig:
                pfsConfig = self.visitManager.activeField.pfsConfig.copy(visit=self.visitId)
                # Write pfsConfig to disk.
                pfsConfigUtils.writePfsConfig(pfsConfig)
                # Insert pfs_config_sps
                opdbUtils.insertPfsConfigSps(pfs_visit_id=self.visitId, visit0=self.visitManager.activeField.visit0)
            else:
                raise RuntimeError('no field has been declared, pfsConfig is unknown...')

            # bump up ag visit whenever sps is taking object.
            if self.exptype == 'object':
                self.iicActor.cmdr.call(actor='ag', cmdStr=f'autoguide reconfigure visit={self.visitId}',
                                        timeLim=10)
        else:
            if self.sequence.lightSource == 'sunss':
                designId = 0xdeadbeef
            else:
                designId = self.iicActor.models[self.sequence.lightSource].keyVarDict['designId'].getValue()

            # Construct dirName from pfsDesign root directory and lightSource.
            dirName = os.path.join(self.iicActor.actorConfig['pfsDesign']['rootDir'], self.sequence.lightSource)
            # Write pfsConfig to disk.
            pfsConfigUtils.writePfsConfigFromDesign(self.visitId, designId, dirName=dirName)

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
        lampsActor = sequence.lightSource.lampsActor
        SubCmd.__init__(self, sequence, lampsActor, *args, **kwargs)

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
        if not sequence.lightSource.isDcb:
            raise RuntimeError('this command has been designed for dcb only')

        LampsCmd.__init__(self, sequence, *args, **kwargs)
