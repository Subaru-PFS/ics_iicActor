import time

from ics.iicActor.utils import stripQuotes, stripField


class SubCmd(object):
    """ Placeholder to handle subcommand processing, status and error"""

    def __init__(self, actor, cmdStr, timeLim, idleTime):
        object.__init__(self)
        self.actor = actor
        self.cmdStr = cmdStr
        self.timeLim = timeLim
        self.idleTime = idleTime
        self.didFail = -1
        self.id = 0
        self.lastReply = ''
        self.visit = -1

    @property
    def fullCmd(self):
        return (f'{self.actor} {self.cmdStr}').strip()

    @property
    def isLast(self):
        return self.sequence.subCmds[-1] == self

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
        cmdVar = self.sequence.actor.cmdr.call(**(self.build(cmd=cmd)))
        return int(cmdVar.didFail), cmdVar.replyList[-1].keywords.canonical(delimiter=';'), cmdVar

    def callAndUpdate(self, cmd):
        """ Call subcommand, handle reply and generate status """
        self.didFail, self.lastReply, cmdVar = self.call(cmd)
        self.inform(cmd=cmd)
        return cmdVar

    def inform(self, cmd):
        """ Generate subcommand status """
        cmd.inform(
            f'subCommand={self.sequence.id},{self.id},"{self.fullCmd}",{self.didFail},"{stripQuotes(self.lastReply)}"')

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

    def __init__(self, *args, **kwargs):
        SubCmd.__init__(self, *args, **kwargs)

    def build(self, cmd):
        """ Build kwargs for actorcore.CmdrConnection.Cmdr.call(**kwargs), format with self.visit """
        return dict(actor=self.actor, cmdStr=self.cmdStr.format(visit=self.visit), forUserCmd=cmd, timeLim=self.timeLim)

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
        ourVisit = self.sequence.actor.visitor.newVisit('sps')
        return ourVisit.visitId

    def releaseVisit(self):
        """ Release visit """
        self.sequence.actor.visitor.releaseVisit()

    def abort(self, cmd):
        ret = self.sequence.actor.cmdr.call(actor='sps',
                                            cmdStr='exposure abort',
                                            forUserCmd=cmd,
                                            timeLim=10)
        if ret.didFail:
            cmd.warn(ret.replyList[-1].keywords.canonical(delimiter=';'))
            raise RuntimeError("Failed to abort exposure")

    def finish(self, cmd):
        ret = self.sequence.actor.cmdr.call(actor='sps',
                                            cmdStr='exposure finish',
                                            forUserCmd=cmd,
                                            timeLim=10)
        if ret.didFail:
            cmd.warn(ret.replyList[-1].keywords.canonical(delimiter=';'))
            raise RuntimeError("Failed to finish exposure")


class DualCmd(SpsExpose):
    def __init__(self, actor, cmdStr, timeLim=300, idleTime=5.0):
        cls = SpsExpose if 'sps expose' in f'{actor} {cmdStr}' else SubCmd
        cls.__init__(self, actor=actor, cmdStr=cmdStr, timeLim=timeLim, idleTime=idleTime)


class Sequence(list):
    """ Placeholder to handle sequence of subcommand """

    def __init__(self, seqtype, name='', comments='', head=None, tail=None):
        self.seqtype = seqtype
        self.name = name
        self.comments = comments
        self.head = Head(head)
        self.tail = Tail(tail)
        self.id = 1
        self.aborted = False

    @property
    def cmdList(self):
        return [item for item in self.__iter__()]

    @property
    def subCmds(self):
        return self.head + self.cmdList + self.tail

    @property
    def visits(self):
        return [subCmd.visit for subCmd in self.subCmds if subCmd.visit != -1]

    @property
    def current(self):
        return self.subCmds[[sub.didFail for sub in self.subCmds].index(-1)]

    def addSubCmd(self, actor, cmdStr, duplicate=1, timeLim=300, idleTime=5.0):
        """ Append duplicate * subcommand to sequence """
        for i in range(duplicate):
            self.append(DualCmd(actor=actor, cmdStr=cmdStr, timeLim=timeLim, idleTime=idleTime))

    def inform(self, cmd):
        """ Generate sps_sequence status """
        cmd.inform(f'sps_sequence={self.id},{self.seqtype},"{self.cmdStr}","{self.name}","{self.comments}"')

    def register(self, cmd):
        """ Register sequence and underlying subcommand"""
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

        finally:
            for subCmd in self.tail:
                self.processSubCmd(cmd, subCmd=subCmd, doRaise=False)

            self.store()

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
            return

        cmdErrors = [r.keywords.canonical(delimiter=';') for r in cmdVar.replyList]

        for cmdError in cmdErrors:
            cmd.warn(cmdError)

    def waitUntil(self, endTime, ti=0.01):
        """ Wait Until endTime"""
        while time.time() < endTime:
            if self.aborted:
                break
            time.sleep(ti)

        return self.aborted

    def start(self, iicActor, cmd):
        """ Register, process and clear sequence """
        self.actor = iicActor
        self.register(cmd=cmd)
        self.process(cmd=cmd)
        self.clear()

    def clear(self):
        """ Clear sequence"""
        del self.head
        del self.tail
        list.clear(self)

    def abort(self, cmd):
        """ Abort current sequence """
        self.aborted = True
        self.current.abort(cmd=cmd)

    def finish(self, cmd):
        """ Finish current sequence """
        self.aborted = True
        self.current.finish(cmd=cmd)

    def store(self):
        """ Store sequence in database """
        if self.visits:
            pass


class Head(Sequence):
    def __init__(self, cmdList=None):
        cmdList = [] if cmdList is None else cmdList

        for fullCmd in cmdList:
            actor, cmdStr = fullCmd.split(' ', 1)
            self.addSubCmd(actor=actor, cmdStr=cmdStr)


class Tail(Sequence):
    def __init__(self, cmdList=None):
        cmdList = [] if cmdList is None else cmdList

        for fullCmd in cmdList:
            actor, cmdStr = fullCmd.split(' ', 1)
            self.addSubCmd(actor=actor, cmdStr=cmdStr)
