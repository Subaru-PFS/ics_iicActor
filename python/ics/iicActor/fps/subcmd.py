from ics.iicActor.utils.lib import stripQuotes
from ics.iicActor.utils.subcmd import SubCmd


class FpsCmd(SubCmd):
    """ Placeholder to handle dcb command specificities"""

    def __init__(self, cmdStr, timeLim=120, **kwargs):
        SubCmd.__init__(self, 'fps', cmdStr, timeLim=timeLim, visit='{visit}', **kwargs)

    def build(self, cmd):
        """ Build kwargs for actorcore.CmdrConnection.Cmdr.call(**kwargs), format with self.visit """
        return dict(actor=self.actor, cmdStr=self.cmdStr.format(visit=self.visit), forUserCmd=None, timeLim=self.timeLim)

    def call(self, cmd):
        """ Get visit from gen2, Call subcommand, release visit """
        try:
            self.visit = self.getVisit()
        except Exception as e:
            return 1, stripQuotes(str(e)), None

        ret = SubCmd.call(self, cmd)
        self.releaseVisit()
        return ret

    def callAndUpdate(self, cmd):
        """Hackity hack, report from sps exposure warning, but"""
        cmdVar = SubCmd.callAndUpdate(self, cmd)
        if cmdVar is not None:
            for reply in cmdVar.replyList:
                if reply.header.code == 'W' and not cmdVar.didFail:
                    cmd.warn(reply.keywords.canonical(delimiter=';'))

        return cmdVar

    def getVisit(self):
        """ Get visit from ics.iicActor.visit.Visit """
        ourVisit = self.sequence.job.visitor.newVisit('fps')
        return ourVisit.visitId

    def releaseVisit(self):
        """ Release visit """
        self.sequence.job.visitor.releaseVisit()

    def abort(self, cmd):
        """ Abort current exposure """
        pass

    def finish(self, cmd):
        """ Finish current exposure """
        pass