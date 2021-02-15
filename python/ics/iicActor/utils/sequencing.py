import time
from functools import partial

from ics.iicActor.utils.lib import stripQuotes, stripField
from opdb import utils, opdb
from opscore.utility.qstr import qstr


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

    def setId(self, sequence, cmdId):
        """ Assign sequence and id to subcommand """
        self.sequence = sequence
        self.id = cmdId

    def build(self, cmd):
        """ Build kwargs for actorcore.CmdrConnection.Cmdr.call(**kwargs) """
        return dict(actor=self.actor,
                    cmdStr=self.cmdStr,
                    forUserCmd=cmd,
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
                    forUserCmd=cmd, timeLim=self.timeLim)

    def call(self, cmd):
        """ Get visit from gen2, Call subcommand, release visit """
        try:
            self.visit = self.getVisit()
        except Exception as e:
            return 1, stripQuotes(str(e)), None

        ret = SubCmd.call(self, cmd)
        self.releaseVisit()
        return ret

    def getVisit(self):
        """ Get visit from ics.iicActor.visit.Visit """
        ourVisit = self.sequence.job.visitor.newVisit('sps')
        return ourVisit.visitId

    def releaseVisit(self):
        """ Release visit """
        self.sequence.job.visitor.releaseVisit()

    def abort(self, cmd):
        """ Abort current exposure """
        ret = self.iicActor.cmdr.call(actor='sps',
                                      cmdStr=f'exposure abort visit={self.visit}',
                                      forUserCmd=cmd,
                                      timeLim=10)
        if ret.didFail:
            cmd.warn(ret.replyList[-1].keywords.canonical(delimiter=';'))
            raise RuntimeError("Failed to abort exposure")

    def finish(self, cmd):
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

    def abort(self, cmd):
        """ Abort warmup """
        ret = self.iicActor.cmdr.call(actor='dcb',
                                      cmdStr='sources abort',
                                      forUserCmd=cmd,
                                      timeLim=10)
        if ret.didFail:
            cmd.warn(ret.replyList[-1].keywords.canonical(delimiter=';'))
            raise RuntimeError("Failed to abort exposure")


class Sequence(list):
    """ Placeholder to handle sequence of subcommand """
    lightBeam = True
    shutterRequired = True

    def __init__(self, seqtype, name='', comments='', head=None, tail=None):
        super().__init__()
        self.seqtype = seqtype
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

    def expose(self, exptype, exptime=0.0, duplicate=1, doLamps=False, **identKeys):
        """ Append duplicate * sps expose to sequence """
        exptime = [exptime] if not isinstance(exptime, list) else exptime

        for expTime in exptime:
            for i in range(duplicate):
                self.append(SpsExpose.specify(exptype, expTime, doLamps=doLamps, **identKeys))

    def add(self, actor, cmdStr, timeLim=60, idleTime=5.0, index=None, **kwargs):
        """ Append duplicate * subcommand to sequence """
        func = self.append if index is None else partial(self.insert, index)
        cls = DcbCmd if actor == 'dcb' else SubCmd
        func(cls(actor, cmdStr, timeLim=timeLim, idleTime=idleTime, **kwargs))

    def inform(self, cmd):
        """ Generate sps_sequence status """
        cmd.inform(f'sps_sequence={self.visit_set_id},{self.seqtype},"{self.cmdStr}","{self.name}","{self.comments}"')

    def register(self, cmd):
        """ Register sequence and underlying subcommand"""
        self.rawCmd = cmd.rawCmd
        self.cmdStr = f"iic {stripQuotes(stripField(stripField(cmd.rawCmd, 'name='), 'comments='))}"
        self.inform(cmd=cmd)

        for cmdId, subCmd in enumerate(self.subCmds):
            subCmd.setId(self, cmdId=cmdId)
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
        self.processSubCmd(cmd, subCmd=subCmd)

        while not (self.doAbort or self.doFinish):
            self.archiveAndReset(cmd, subCmd)
            self.processSubCmd(cmd, subCmd=subCmd)

        self.store()

    def archiveAndReset(self, cmd, subCmd):
        """ archive a copy of the current command then reset it."""
        self.insert(subCmd.id, subCmd.copy())
        subCmd.initialise()
        subCmd.setId(self, len(self.cmdList) - 1)
        subCmd.inform(cmd=cmd)

    def processSubCmd(self, cmd, subCmd, doRaise=True):
        """ Process each subcommand, handle error or abortion """
        cmdVar = subCmd.callAndUpdate(cmd=cmd)

        if subCmd.didFail and doRaise:
            self.handleError(cmd=cmd, cmdId=subCmd.id, cmdVar=cmdVar)
            raise RuntimeError('Sub-command has failed.. sequence aborted..')

        if subCmd.isLast:
            return

        aborted = self.waitUntil(time.time() + subCmd.idleTime)

        if aborted and doRaise:
            self.handleError(cmd=cmd, cmdId=subCmd.id)
            raise RuntimeError('Abort sequence requested..')

    def handleError(self, cmd, cmdId, cmdVar=None):
        """ Release remaining subcommand, generate warnings"""
        for id in range(cmdId + 1, len(self.head + self.cmdList)):
            self.subCmds[id].didFail = 1
            self.subCmds[id].inform(cmd)

        if cmdVar is None:
            cmdErrors = [f'text={qstr(self.subCmds[cmdId].lastReply)}']
        else:
            cmdErrors = [r.keywords.canonical(delimiter=';') for r in cmdVar.replyList]

        self.errorTrace = ';'.join(cmdErrors)

        for cmdError in cmdErrors:
            cmd.warn(cmdError)

    def waitUntil(self, endTime, ti=0.01):
        """ Wait Until endTime"""
        while time.time() < endTime:
            if self.doFinish or self.doAbort:
                break

            time.sleep(ti)

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
