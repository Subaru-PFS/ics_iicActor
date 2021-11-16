import time
from functools import partial

from ics.iicActor.utils.lib import stripQuotes, stripField, wait
from ics.utils.opdb import opDB
from iicActor.utils.subcmd import SubCmd
from opscore.utility.qstr import qstr


class Sequence(list):
    """ Placeholder to handle sequence of subcommand """
    seqtype = 'sequence'

    def __init__(self, name='', comments='', head=None, tail=None):
        super().__init__()
        self.name = name
        self.comments = comments
        self.head = CmdList(self, head)
        self.tail = CmdList(self, tail)
        self.isDone = False
        self.doAbort = False
        self.doFinish = False
        self.errorTrace = ''

    @property
    def didFail(self):
        return bool(self.errorTrace)

    @property
    def statusStr(self):
        if not self.isDone:
            return 'active'
        else:
            if self.doAbort:
                return 'aborted'
            elif self.didFail:
                return 'failed'
            else:
                return 'finished'

    @property
    def output(self):
        if not self.isDone:
            return ''
        if self.didFail and not self.doAbort:
            return self.errorTrace
        elif self.doAbort:
            return 'abortRequested'
        elif self.doFinish:
            return 'finishRequested'
        else:
            return 'complete'

    @property
    def cmdList(self):
        return [item for item in self.__iter__()]

    @property
    def subCmds(self):
        return self.head + self.cmdList + self.tail

    @property
    def visits(self):
        return [subCmd.visit for subCmd in self.subCmds if subCmd.visited]

    @property
    def visitStart(self):
        return min(self.visits) if self.visits else None

    @property
    def visitEnd(self):
        return max(self.visits) if self.visits else None

    @property
    def current(self):
        return self.subCmds[[sub.didFail for sub in self.subCmds].index(-1)]

    @property
    def visit_set_id(self):
        return self.job.visitSetId

    @property
    def iicActor(self):
        return self.job.actor

    def assign(self, cmd, job):
        """ get last visit_set_id from opDB """
        self.job = job
        self.register(cmd)

    def add(self, actor, cmdStr, timeLim=60, idleTime=1.0, index=None, **kwargs):
        """ Append duplicate * subcommand to sequence """
        func = self.append if index is None else partial(self.insert, index)
        cls = self.guessType(actor, cmdStr)
        func(cls(actor, cmdStr, timeLim=timeLim, idleTime=idleTime, **kwargs))

    def guessType(self, actor, cmdStr):
        """ Guess SubCmd type """
        return SubCmd

    def guessTimeLim(self, cmdStr, timeLim=0):
        """ Guess timeLim """
        return 60

    def genKeys(self):
        return f'sequence={self.visit_set_id},{self.seqtype},{self.statusStr},"{self.cmdStr}","{self.name}","{self.comments}"'

    def register(self, cmd):
        """ Register sequence and underlying subcommand"""
        self.rawCmd = cmd.rawCmd
        self.cmdStr = f"iic {stripQuotes(stripField(stripField(cmd.rawCmd, 'name='), 'comments='))}"
        cmd.inform(self.genKeys())

        for cmdId, subCmd in enumerate(self.subCmds):
            subCmd.register(self, cmdId=cmdId)
            subCmd.inform(cmd=cmd)

    def process(self, cmd):
        """ Process full sequence, store in database"""
        self.insertSequence()
        try:
            self.commandLogic(cmd)
        finally:
            self.finalize(cmd)

    def commandLogic(self, cmd):
        """ Process full sequence, store in database"""
        try:
            for subCmd in (self.head + self.cmdList):
                self.processSubCmd(cmd, subCmd=subCmd)

                if self.doFinish:
                    break

        finally:
            for subCmd in self.tail:
                self.processSubCmd(cmd, subCmd=subCmd, doRaise=False)

    def processSubCmd(self, cmd, subCmd, doRaise=True):
        """ Process one subcommand, handle error or abortion """
        cmdVar = subCmd.callAndUpdate(cmd)

        self.genProperOutput(cmd, didFail=subCmd.didFail, subCmd=subCmd, cmdVar=cmdVar, doRaise=doRaise)

        if not subCmd.isLast:
            aborted = self.waitUntil(time.time() + subCmd.idleTime)
            self.genProperOutput(cmd, didFail=aborted, subCmd=subCmd)

    def genProperOutput(self, cmd, didFail, subCmd, cmdVar=None, doRaise=True):
        """ Process one subcommand, handle error or abortion """
        doRaise = False if self.doFinish else doRaise

        if didFail or self.doFinish:
            self.cancelRemainings(cmd, cmdId=subCmd.id)
            if doRaise:
                self.handleError(cmd, cmdId=subCmd.id, cmdVar=cmdVar)
                if self.doAbort:
                    raise RuntimeError('abort sequence requested...')
                else:
                    raise RuntimeError('Sub-command has failed.. sequence stopping now !!!')

    def handleError(self, cmd, cmdId, cmdVar=None):
        """ Catch error(s) and generate warnings"""
        if cmdVar is None:
            cmdErrors = [f'text={qstr(self.subCmds[cmdId].lastReply)}']
        else:
            cmdErrors = [r.keywords.canonical(delimiter=';') for r in cmdVar.replyList]

        self.errorTrace = ';'.join(cmdErrors)

        for cmdError in cmdErrors:
            cmd.warn(cmdError)

    def cancelRemainings(self, cmd, cmdId):
        """ Release remaining subcommand"""
        for id in range(cmdId + 1, len(self.head + self.cmdList)):
            self.subCmds[id].didFail = 1
            self.subCmds[id].inform(cmd)

    def waitUntil(self, endTime):
        """ Wait Until endTime"""
        while time.time() < endTime:
            if self.doFinish or self.doAbort:
                break

            wait()

        return self.doAbort

    def clear(self):
        """ Clear sequence"""
        del self.head
        del self.tail
        list.clear(self)

    def abort(self, cmd):
        """ Abort current sequence """
        self.doAbort = True
        self.current.abort(cmd=cmd)

    def finish(self, cmd, **kwargs):
        """ Finish current sequence """
        self.doFinish = True
        self.current.finish(cmd=cmd)

    def insertSequence(self):
        """ Store sequence in database """
        opDB.insert('iic_sequence',
                    visit_set_id=self.visit_set_id, sequence_type=self.seqtype, name=self.name,
                    comments=self.comments, cmd_str=self.rawCmd)

    def finalize(self, cmd):
        """ Store sequence in database """
        self.isDone = True
        cmd.inform(self.genKeys())
        opDB.insert('iic_sequence_status',
                    visit_set_id=self.visit_set_id, status_flag=int(self.didFail), cmd_output=self.output)


class CmdList(Sequence):
    def __init__(self, sequence, cmdList):
        cmdList = [] if cmdList is None else cmdList

        self.sequence = sequence

        for fullCmd in cmdList:
            self.autoadd(fullCmd)

    def autoadd(self, fullCmd):
        """ Append duplicate * subcommand to sequence """
        actor, cmdStr = fullCmd.split(' ', 1)
        if actor == 'iic':
            raise ValueError('cannot call iic recursively !')

        cls = self.sequence.guessType(actor, cmdStr)
        timeLim = self.sequence.guessTimeLim(cmdStr)
        self.append(cls(actor, cmdStr, timeLim=timeLim))
