import time
from functools import partial

from ics.iicActor.utils.lib import stripQuotes, stripField, wait
from iicActor.utils.subcmd import SubCmd, DcbCmd, SpsExpose
from opdb import utils, opdb
from opscore.utility.qstr import qstr


class Sequence(list):
    """ Placeholder to handle sequence of subcommand """
    seqtype = 'sequence'
    lightBeam = True
    shutterRequired = True
    doCheckFocus = False

    def __init__(self, name='', comments='', head=None, tail=None):
        super().__init__()
        self.name = name
        self.comments = comments
        self.head = CmdList(head)
        self.tail = CmdList(tail)
        self.doAbort = False
        self.doFinish = False
        self.errorTrace = ''

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
    def status(self):
        if self.doAbort:
            return 'abortRequested'
        elif self.doFinish:
            return 'finishRequested'
        elif self.errorTrace:
            return self.errorTrace
        else:
            return 'complete'

    @property
    def exposable(self):
        try:
            cams = self.job.actor.models['sps'].keyVarDict['exposable'].getValue()
        except:
            return None

        return ','.join(cams)

    @property
    def visit_set_id(self):
        return self.job.visitSetId

    def assign(self, cmd, job):
        """ get last visit_set_id from opDB """
        self.job = job
        self.register(cmd)

    def expose(self, exptype, exptime=0.0, duplicate=1, doTest=False, **identKeys):
        """ Append duplicate * sps expose to sequence """
        exptime = [exptime] if not isinstance(exptime, list) else exptime

        for expTime in exptime:
            for i in range(duplicate):
                self.append(SpsExpose.specify(exptype, expTime, doTest=doTest, **identKeys))

    def add(self, actor, cmdStr, timeLim=60, idleTime=5.0, index=None, **kwargs):
        """ Append duplicate * subcommand to sequence """
        func = self.append if index is None else partial(self.insert, index)
        cls = DcbCmd if actor == 'dcb' else SubCmd
        func(cls(actor, cmdStr, timeLim=timeLim, idleTime=idleTime, **kwargs))

    def inform(self, cmd):
        """ Generate sps_sequence status """
        cmd.inform(self.genKeys())

    def genKeys(self):
        return f'sps_sequence={self.visit_set_id},{self.seqtype},"{self.cmdStr}","{self.name}","{self.comments}",{self.job.getStatus()}'

    def register(self, cmd):
        """ Register sequence and underlying subcommand"""
        self.rawCmd = cmd.rawCmd
        self.cmdStr = f"iic {stripQuotes(stripField(stripField(cmd.rawCmd, 'name='), 'comments='))}"
        self.inform(cmd=cmd)

        for cmdId, subCmd in enumerate(self.subCmds):
            subCmd.register(self, cmdId=cmdId)
            subCmd.inform(cmd=cmd)

    def process(self, cmd):
        """ Process full sequence, store in database"""

        try:
            for subCmd in (self.head + self.cmdList):
                self.processSubCmd(cmd, subCmd=subCmd)

                if self.doFinish:
                    break

        finally:
            for subCmd in self.tail:
                self.processSubCmd(cmd, subCmd=subCmd, doRaise=False)

            self.store()

    def loop(self, cmd):
        """ loop the command until being told to stop, store in database"""
        [subCmd] = self.cmdList

        try:
            self.processSubCmd(cmd, subCmd=subCmd)

            while not (self.doFinish or self.doAbort):
                self.archiveAndReset(cmd, subCmd)
                self.processSubCmd(cmd, subCmd=subCmd)

        finally:
            self.store()

    def archiveAndReset(self, cmd, subCmd):
        """ archive a copy of the current command then reset it."""
        self.insert(subCmd.id, subCmd.copy())
        subCmd.initialise()
        subCmd.register(self, len(self.cmdList) - 1)
        subCmd.inform(cmd=cmd)

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

    def finish(self, cmd):
        """ Finish current sequence """
        self.doFinish = True
        self.current.finish(cmd=cmd)

    def store(self):
        """ Store sequence in database """
        if self.visits:
            utils.insert_row(opdb.OpDB.url, 'sps_sequence', visit_set_id=self.visit_set_id, sequence_type=self.seqtype,
                             name=self.name, comments=self.comments, cmd_str=self.rawCmd, status=self.status)

            for visit in self.visits:
                utils.insert_row(opdb.OpDB.url, 'visit_set', pfs_visit_id=visit, visit_set_id=self.visit_set_id)


class CmdList(Sequence):
    def __init__(self, cmdList):
        cmdList = [] if cmdList is None else cmdList

        for fullCmd in cmdList:
            self.autoadd(fullCmd)

    def autoadd(self, fullCmd):
        """ Append duplicate * subcommand to sequence """
        actor, cmdStr = fullCmd.split(' ', 1)
        if actor == 'iic':
            raise ValueError('cannot call iic recursively !')

        cls = self.guessType(actor, cmdStr)
        timeLim = self.guessTimeLim(cmdStr)
        self.append(cls(actor, cmdStr, timeLim=timeLim))

    def guessType(self, actor, cmdStr):
        """ Guess SubCmd type """
        if actor == 'dcb':
            cls = DcbCmd
        elif actor == 'sps' and 'expose' in cmdStr:
            cls = SpsExpose
        else:
            cls = SubCmd

        return cls

    def guessTimeLim(self, cmdStr, timeLim=0):
        """ Guess timeLim """
        keys = ['warmingTime', 'exptime']
        args = cmdStr.split(' ')
        for arg in args:
            for key in keys:
                try:
                    __, timeLim = arg.split(f'{key}=')
                except ValueError:
                    pass

        return int(float(timeLim)) + 60
