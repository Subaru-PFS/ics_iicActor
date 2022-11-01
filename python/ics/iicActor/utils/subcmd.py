import ics.utils.cmd as cmdUtils
from ics.iicActor.utils.exception import IicException
from ics.iicActor.utils.lib import stripQuotes


class CmdRet(object):
    """Putting more"""

    def __init__(self, status, replyList, lastReply):
        self.status = status
        self.replyList = replyList
        self.lastReply = lastReply

    def __str__(self):
        return f'{self.status},"{self.lastReply}"'

    @property
    def didFail(self):
        return self.status == 1

    @property
    def wasCalled(self):
        return self.status != -1

    @classmethod
    def fromCmdVar(cls, cmdVar):
        lastReply = cmdUtils.interpretFailure(cmdVar) if cmdVar.didFail else cmdUtils.formatLastReply(cmdVar)
        return cls(int(cmdVar.didFail), cmdVar.replyList, stripQuotes(lastReply))

    def cancel(self):
        """Set status and reply for keyword generation."""
        self.status = 1
        self.lastReply = 'cancelled'


class SubCmd(object):
    """ Placeholder to handle subcommand processing, status and error"""

    def __init__(self, sequence, actor, cmdStr, timeLim=60, **kwargs):
        object.__init__(self)
        cmdStr = cmdUtils.parse(cmdStr, **kwargs)

        self.sequence = sequence
        self.actor = actor
        self.cmdStr = cmdStr
        self.cmdHead = cmdStr if cmdStr.find(' ') == -1 else cmdStr[:cmdStr.find(' ')]
        self.timeLim = timeLim

        # initialize empty cmdRet
        self.id = -1
        self.cmdRet = CmdRet(-1, [''], '')

    def __str__(self):
        return f'subCommand={self.sequence.sequence_id},{self.id},"{self.fullCmd}",{self.cmdRet}'

    @property
    def fullCmd(self):
        return f'{self.actor} {self.cmdStr}'.strip()

    @property
    def iicActor(self):
        return self.sequence.engine.actor

    def build(self, cmd):
        """ Build kwargs for actorcore.CmdrConnection.Cmdr.call(**kwargs) """
        return dict(actor=self.actor,
                    cmdStr=self.cmdStr,
                    forUserCmd=cmd,
                    timeLim=self.timeLim)

    def callAndUpdate(self, cmd):
        """"""
        self.cmdRet = self.call(cmd)
        self.handleOutput(cmd)

    def call(self, cmd):
        """ Call subcommand, handle reply and generate status """
        cmdVar = self.iicActor.cmdr.call(**(self.build(cmd=cmd)))
        cmdRet = CmdRet.fromCmdVar(cmdVar)

        # report warnings
        warnings = [reply for reply in cmdRet.replyList[:-1] if reply.header.code == 'W']
        for warning in warnings:
            cmd.warn(warning.keywords.canonical(delimiter=';'))

        return cmdRet

    def handleOutput(self, cmd):
        """"""
        self.genKeys(cmd)

        if self.cmdRet.didFail:
            raise IicException(reason=self.cmdRet.lastReply,
                               className=f'{self.actor.capitalize()}{self.cmdHead.capitalize()}')

    def genKeys(self, cmd):
        """"""
        genKeys = cmd.warn if self.cmdRet.didFail else cmd.inform
        genKeys(str(self))

    def init(self, id, cmd):
        """"""
        self.id = id
        self.genKeys(cmd)

    def cancel(self, cmd):
        """"""
        self.cmdRet.cancel()
        self.genKeys(cmd)

    def abort(self, cmd):
        """ abort prototype"""

    def finishNow(self, cmd):
        """ finish prototype"""
