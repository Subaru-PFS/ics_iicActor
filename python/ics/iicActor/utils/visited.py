import ics.iicActor.utils.opdb as opdbUtils
from ics.iicActor.utils.sequence import Sequence
from ics.iicActor.utils.subcmd import SubCmd


class VisitedCmd(SubCmd):
    visitCmdArg = 'visit'
    frameIdCmdArg = 'frameId'

    def __init__(self, *args, parseVisit=False, parseFrameId=False, **kwargs):
        SubCmd.__init__(self, *args, **kwargs)

        self.parseVisit = parseVisit
        self.parseFrameId = parseFrameId

        self.allocatedFrameId = -1

    @property
    def visitManager(self):
        return self.iicActor.engine.visitManager

    @property
    def visitId(self):
        visitId = -1 if self.sequence.visit is None else self.sequence.visit.visitId
        return visitId

    @property
    def frameId(self):
        frameId = -1 if self.sequence.visit is None else self.allocateFrameId()
        return frameId

    @property
    def cmdStrAndVisit(self):
        """Parse visit or frameId"""
        allArgs = [self.cmdStr]
        allArgs.extend([f'{self.visitCmdArg}={self.visitId}'] if self.parseVisit else [])
        allArgs.extend([f'{self.frameIdCmdArg}={self.frameId}'] if self.parseFrameId else [])
        return ' '.join(allArgs).strip()

    @property
    def fullCmd(self):
        return f'{self.actor} {self.cmdStrAndVisit}'

    def build(self, cmd):
        """ Build kwargs for actorcore.CmdrConnection.Cmdr.call(**kwargs), format with self.visitId """
        return dict(actor=self.actor, cmdStr=self.cmdStrAndVisit, forUserCmd=self.forUserCmd(cmd), timeLim=self.timeLim)

    def allocateFrameId(self):
        """Allocate frameId only once."""
        if self.allocatedFrameId == -1:
            self.allocatedFrameId = self.sequence.visit.nextFrameId()

        return self.allocatedFrameId


class VisitedSequence(Sequence):
    """Define a sequence combined with a single visit, fps/ag inherit from this, not sps."""
    caller = ''

    def __init__(self, **seqKeys):
        self.visit = None
        Sequence.__init__(self, **seqKeys)

    def instantiate(self, actor, cmdStr, parseVisit=False, parseFrameId=False, **kwargs):
        """Just return VisitedCmd always"""
        # I could have return VisitedCmd only if (parseVisit or parseFrameId) but it strictly the same.
        return VisitedCmd(self, actor, cmdStr, parseVisit=parseVisit, parseFrameId=parseFrameId, **kwargs)

    def activate(self):
        """Get, attach and lock visit, and then regular Sequence.activate()."""
        # prior to activate sequence, get a visit and lock it.
        self.visit = self.engine.visitManager.getVisit(self.caller)
        self.visit.lock()
        return Sequence.activate(self)

    def finalize(self):
        """Unlock visit, regular Sequence.finalize() and insert into visit_set."""
        # prior to finalize sequence, unlock visit.
        self.visit.unlock()
        Sequence.finalize(self)
        # finally insert into visit_set table
        opdbUtils.insertVisitSet(self.caller, sequence_id=self.sequence_id, pfs_visit_id=self.visit.visitId)
