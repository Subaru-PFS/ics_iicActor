from ics.iicActor.utils.lib import stripQuotes
from ics.iicActor.utils.subcmd import SubCmd

class SpsExpose(SubCmd):
    """ Placeholder to handle sps expose command specificities"""

    def __init__(self, actor, cmdStr, timeLim=120, **kwargs):
        SubCmd.__init__(self, actor, cmdStr, timeLim=timeLim, visit='{visit}', **kwargs)

    @classmethod
    def specify(cls, exptype, exptime, **kwargs):
        timeLim = 120 + exptime
        exptime = exptime if exptime else None
        return cls('sps', f'expose {exptype}', timeLim=timeLim, exptime=exptime, **kwargs)

    def build(self, cmd):
        """ Build kwargs for actorcore.CmdrConnection.Cmdr.call(**kwargs), format with self.visit """
        return dict(actor=self.actor, cmdStr=self.cmdStr.format(visit=self.visit, cams=self.sequence.exposable),
                    forUserCmd=None, timeLim=self.timeLim)

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
        ourVisit = self.sequence.job.visitor.newVisit('sps')
        return ourVisit.visitId

    def releaseVisit(self):
        """ Release visit """
        self.sequence.job.visitor.releaseVisit()

    def abort(self, cmd):
        """ Abort current exposure """
        if self.visit == -1:
            return

        ret = self.iicActor.cmdr.call(actor='sps',
                                      cmdStr=f'exposure abort visit={self.visit}',
                                      forUserCmd=cmd,
                                      timeLim=10)
        if ret.didFail:
            cmd.warn(ret.replyList[-1].keywords.canonical(delimiter=';'))
            raise RuntimeError("Failed to abort exposure")

    def finish(self, cmd):
        """ Finish current exposure """
        if self.visit == -1:
            return

        ret = self.iicActor.cmdr.call(actor='sps',
                                      cmdStr=f'exposure finish visit={self.visit}',
                                      forUserCmd=cmd,
                                      timeLim=10)
        if ret.didFail:
            cmd.warn(ret.replyList[-1].keywords.canonical(delimiter=';'))
            raise RuntimeError("Failed to finish exposure")


class DcbCmd(SubCmd):
    """ Placeholder to handle dcb command specificities"""

    def __init__(self, *args, **kwargs):
        SubCmd.__init__(self, *args, **kwargs)

    @property
    def dcbActor(self):
        return self.sequence.job.lightSource

    def build(self, cmd):
        """ Override dcbActor with actual lightSource """

        return dict(actor=self.dcbActor,
                    cmdStr=self.cmdStr,
                    forUserCmd=None,
                    timeLim=self.timeLim)


    def abort(self, cmd):
        """ Abort warmup """
        ret = self.iicActor.cmdr.call(actor=self.dcbActor,
                                      cmdStr='sources abort',
                                      forUserCmd=cmd,
                                      timeLim=10)
        if ret.didFail:
            cmd.warn(ret.replyList[-1].keywords.canonical(delimiter=';'))
            raise RuntimeError("Failed to abort exposure")
