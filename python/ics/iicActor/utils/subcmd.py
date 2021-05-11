from ics.iicActor.utils.lib import stripQuotes


class SubCmd(object):
    """ Placeholder to handle subcommand processing, status and error"""

    def __init__(self, actor, cmdStr, timeLim=60, idleTime=5.0, **kwargs):
        object.__init__(self)
        cmdStr = ' '.join([cmdStr] + SubCmd.parse(**kwargs))
        self.actor = actor
        self.cmdStr = cmdStr
        self.timeLim = timeLim
        self.idleTime = idleTime
        self.initialise()

    @property
    def fullCmd(self):
        return (f'{self.actor} {self.cmdStr}').strip()

    @property
    def isLast(self):
        return self.sequence.subCmds[-1] == self

    @property
    def visited(self):
        return not self.didFail and self.visit != -1

    @property
    def iicActor(self):
        return self.sequence.job.actor

    @staticmethod
    def parse(**kwargs):
        """ Strip given text field from rawCmd """
        args = []
        for k, v in kwargs.items():
            if v is None or v is False:
                continue
            if isinstance(v, list):
                v = ','.join([str(e) for e in v])
            args.append(k if v is True else f'{k}={v}')

        return args

    def copy(self):
        """ return a subcmd copy """
        obj = SubCmd(self.actor, self.cmdStr)
        obj.id = self.id
        obj.visit = self.visit
        obj.didFail = self.didFail
        obj.lastReply = self.lastReply
        return obj

    def initialise(self):
        """ Reset sub command status"""
        self.didFail = -1
        self.id = 0
        self.lastReply = ''
        self.visit = -1

    def register(self, sequence, cmdId):
        """ Assign sequence and id to subcommand """
        self.sequence = sequence
        self.id = cmdId

    def build(self, cmd):
        """ Build kwargs for actorcore.CmdrConnection.Cmdr.call(**kwargs) """
        return dict(actor=self.actor,
                    cmdStr=self.cmdStr,
                    forUserCmd=None,
                    timeLim=self.timeLim)

    def call(self, cmd):
        """ Call subcommand """
        cmdVar = self.iicActor.cmdr.call(**(self.build(cmd=cmd)))
        return int(cmdVar.didFail), cmdVar.replyList[-1].keywords.canonical(delimiter=';'), cmdVar

    def callAndUpdate(self, cmd):
        """ Call subcommand, handle reply and generate status """
        self.didFail, self.lastReply, cmdVar = self.call(cmd)
        self.inform(cmd=cmd)
        return cmdVar

    def inform(self, cmd):
        """ Generate subcommand status """
        cmd.inform(
            f'subCommand={self.sequence.visit_set_id},{self.id},"{self.fullCmd}",{self.didFail},"{stripQuotes(self.lastReply)}"')

    def abort(self, cmd):
        """ abort prototype"""

    def finish(self, cmd):
        """ finish prototype"""

    def getVisit(self):
        """ getVisit prototype"""
        pass

    def releaseVisit(self):
        """ releaseVisit prototype"""
        pass


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
