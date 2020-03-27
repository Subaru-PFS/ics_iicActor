import time

from ics.iicActor.utils import stripQuotes, stripField


class SubCmd(object):
    """ Placeholder to handle subcommand processing, status and error"""

    def __init__(self, actor, cmdStr, timeLim=300, idleTime=5.0):
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

    def callAndUpdate(self, cmd):
        """ Call subcommand, handle reply and generate status """
        cmdVar = self.sequence.actor.cmdr.call(**(self.build(cmd=cmd)))
        self.didFail = int(cmdVar.didFail)
        self.lastReply = cmdVar.replyList[-1].keywords.canonical(delimiter=';')
        self.visit = self.getVisit(cmdVar)
        self.inform(cmd=cmd)
        return cmdVar

    def inform(self, cmd):
        """ Generate subcommand status """
        cmd.inform(
            f'subCommand={self.sequence.id},{self.id},"{self.fullCmd}",{self.didFail},"{stripQuotes(self.lastReply)}"')

    def getVisit(self, cmdVar):
        """ Retrieve visit from cmdVar """
        visit = -1
        if not self.didFail:
            try:
                visit = int(cmdVar.replyList[-1].keywords['visit'].values[0])
            except KeyError:
                pass

        return visit


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

    def addSubCmd(self, actor, cmdStr, duplicate=1, timeLim=300, idleTime=5.0):
        """ Append duplicate * subcommand to sequence """
        for i in range(duplicate):
            self.append(SubCmd(actor=actor, cmdStr=cmdStr, timeLim=timeLim, idleTime=idleTime))

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

        if cmdVar.didFail and doRaise:
            self.handleError(cmd=cmd, cmdId=subCmd.id, cmdVar=cmdVar)
            raise RuntimeError('subCmd has failed.. sequence aborted..')

        aborted = self.waitUntil(time.time() + subCmd.idleTime)
        if aborted and doRaise:
            self.handleError(cmd=cmd, cmdId=subCmd.id)
            raise RuntimeError('abort sequence requested..')

    def handleError(self, cmd, cmdId, cmdVar=None):
        """ Release remaining subcommand, generate warnings"""
        for id in range(cmdId + 1, len(self.head + self.cmdList)):
            self.subCmds[id].didFail = 1
            self.subCmds[id].inform(cmd)

        if cmdVar is None:
            cmd.warn("""text="command failed: UserWarning('Abort requested') in waitUntil()""")
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

    def abort(self):
        """ Abort current sequence """
        self.aborted = True

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
