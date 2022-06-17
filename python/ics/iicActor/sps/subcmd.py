from ics.iicActor.utils.subcmd import VisitedCmd, SubCmd
from ics.utils.cmd import cmdVarToKeys


class SpsExpose(VisitedCmd):
    """ Placeholder to handle sps expose command specificities"""

    def __init__(self, actor, cmdStr, timeLim=120, **kwargs):
        VisitedCmd.__init__(self, actor, cmdStr, timeLim=timeLim, **kwargs)

    @classmethod
    def specify(cls, exptype, exptime, timeOffset=120, **kwargs):
        timeLim = timeOffset + exptime
        exptime = exptime if exptime else None
        return cls('sps', f'expose {exptype}', timeLim=timeLim, exptime=exptime, **kwargs)

    def visitConsumed(self, cmdVar):
        """Has the visit been consumed."""
        cmdKeys = cmdVarToKeys(cmdVar)
        try:
            visit, __, mask = cmdKeys['fileIds'].values
        except:
            mask = "0x0"

        return int(mask, 16) > 0

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


class LampsCmd(SubCmd):
    """ Placeholder to handle lamps command specificities"""

    def __init__(self, *args, **kwargs):
        SubCmd.__init__(self, *args, **kwargs)

    def build(self, cmd):
        """ Override dcbActor with actual lightSource """

        return dict(actor=self.sequence.job.lightSource.lampsActor,
                    cmdStr=self.cmdStr,
                    forUserCmd=None,
                    timeLim=self.timeLim)

    def abort(self, cmd):
        """ Abort warmup """
        ret = self.iicActor.cmdr.call(actor=self.sequence.job.lightSource.lampsActor,
                                      cmdStr='abort',
                                      forUserCmd=cmd,
                                      timeLim=10)
        if ret.didFail:
            cmd.warn(ret.replyList[-1].keywords.canonical(delimiter=';'))
            raise RuntimeError("Failed to abort exposure")


class DcbCmd(LampsCmd):
    def __init__(self, *args, **kwargs):
        LampsCmd.__init__(self, *args, **kwargs)

    def build(self, cmd):
        """ Override dcbActor with actual lightSource """
        if not self.sequence.job.lightSource.isDcb:
            raise RuntimeError('this command has been designed for dcb only')

        return LampsCmd.build(self, cmd)
