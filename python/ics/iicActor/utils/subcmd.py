from ics.iicActor.utils.lib import stripQuotes
import pfscore.gen2 as gen2


class SubCmd(object):
    """ Placeholder to handle subcommand processing, status and error"""

    def __init__(self, actor, cmdStr, timeLim=60, idleTime=1.0, **kwargs):
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
        return self.sequence.isMainSequence and self.sequence.subCmds[-1] == self

    @property
    def visited(self):
        return not self.didFail and self.visit != -1

    @property
    def iicActor(self):
        return self.sequence.iicActor

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
        self.cmdVar = None
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
        return self.iicActor.cmdr.call(**(self.build(cmd=cmd)))

    def makeOutput(self, cmdVar):
        """ Call subcommand, handle reply and generate status """
        return cmdVar, int(cmdVar.didFail), cmdVar.replyList[-1].keywords.canonical(delimiter=';')

    def warn(self, cmd):
        """ Generate subcommand warnings """
        pass

    def inform(self, cmd):
        """ Generate subcommand status """
        cmd.inform(
            f'subCommand={self.sequence.visit_set_id},{self.id},"{self.fullCmd}",{self.didFail},"{stripQuotes(self.lastReply)}"')

    def genOutput(self, cmd):
        """ Generate subcommand status """
        self.warn(cmd)
        self.inform(cmd)

    def callAndUpdate(self, cmd):
        """ Call subcommand, handle reply and generate status """
        cmdVar = self.call(cmd)
        self.cmdVar, self.didFail, self.lastReply = self.makeOutput(cmdVar)
        self.genOutput(cmd=cmd)
        return cmdVar

    def abort(self, cmd):
        """ abort prototype"""

    def finish(self, cmd):
        """ finish prototype"""


class VisitedCmd(SubCmd):
    """ Placeholder to handle sps expose command specificities"""

    def __init__(self, actor, cmdStr, timeLim=120, **kwargs):
        SubCmd.__init__(self, actor, cmdStr, timeLim=timeLim, visit='{visit}', **kwargs)

    def build(self, cmd):
        """ Build kwargs for actorcore.CmdrConnection.Cmdr.call(**kwargs), format with self.visit """
        return dict(actor=self.actor, cmdStr=self.cmdStr.format(visit=self.visit),
                    forUserCmd=None, timeLim=self.timeLim)

    def warn(self, cmd):
        """ report from sps exposure warning """
        if self.cmdVar is None:
            return

        for reply in self.cmdVar.replyList:
            if reply.header.code == 'W' and not self.cmdVar.didFail:
                cmd.warn(reply.keywords.canonical(delimiter=';'))

    def callAndUpdate(self, cmd):
        """Get visit, expose, release visit."""
        cmdVar = None

        try:
            cmdVar = self.handleVisitAndCall(cmd)
            self.insertDB(cmdVar)
        except gen2.FetchVisitFromGen2 as e:
            self.didFail = 1
            self.lastReply = str(e)
            self.genOutput(cmd=cmd)

        return cmdVar

    def handleVisitAndCall(self, cmd):
        """"""
        with self.iicActor.visitor.getVisit(caller=self.actor) as ourVisit:
            self.visit = ourVisit.visitId
            return SubCmd.callAndUpdate(self, cmd)

    def insertDB(self, cmdVar):
        """"""
        pass
