from ics.iicActor.utils.lib import stripQuotes
from ics.iicActor.utils.subcmd import SubCmd


class FpsCmd(SubCmd):
    """ Placeholder to handle dcb command specificities"""

    def __init__(self, cmdStr, timeLim=120, **kwargs):
        SubCmd.__init__(self, 'fps', cmdStr, timeLim=timeLim, **kwargs, visit='{visit}')

    def build(self, cmd):
        """ Build kwargs for actorcore.CmdrConnection.Cmdr.call(**kwargs), format with self.visit """
        return dict(actor=self.actor, cmdStr=self.cmdStr.format(visit=self.visit), forUserCmd=None, timeLim=self.timeLim)

    def warn(self, cmd):
        """ report from cmd warning """
        if self.cmdVar is None:
            return

        for reply in self.cmdVar.replyList:
            if reply.header.code == 'W' and not self.cmdVar.didFail:
                cmd.warn(reply.keywords.canonical(delimiter=';'))

    def callAndUpdate(self, cmd):
        """Get visit, expose, release visit."""
        try:
            self.visit = self.getVisit()
        except Exception as e:
            self.didFail = 1
            self.lastReply = stripQuotes(str(e))
            self.genOutput(cmd=cmd)
            return None

        cmdVar = SubCmd.callAndUpdate(self, cmd)
        self.releaseVisit()
        return cmdVar

    def getVisit(self):
        """ Get visit from ics.iicActor.visit.Visit """
        ourVisit = self.sequence.job.visitor.newVisit('fps')
        return ourVisit.visitId

    def releaseVisit(self):
        """ Release visit """
        self.sequence.job.visitor.releaseVisit()

        if not self.didFail:
            self.sequence.insertVisitSet(visit=self.visit)

    def abort(self, cmd):
        """ Abort current exposure """
        pass

    def finish(self, cmd):
        """ Finish current exposure """
        pass
