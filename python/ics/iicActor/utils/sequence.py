import ics.iicActor.utils.opdb as opdbUtils
import ics.utils.time as pfsTime
from ics.iicActor.utils.lib import makeCmdStr
from ics.iicActor.utils.subcmd import SubCmd
from iicActor.utils import exception
from iicActor.utils.sequenceStatus import Status, Flag


class Sequence(list):
    daysToDeclareObsolete = 7
    seqtype = 'sequence'

    def __init__(self, name="", comments="", doTest=False, noDeps=False, forceGrating=False,
                 head=None, tail=None, groupId=None, cmdKeys=None):
        super().__init__()
        self.name = name
        self.comments = comments
        self.doTest = doTest
        self.noDeps = noDeps
        self.forceGrating = forceGrating
        self.head = CmdList(self, head)
        self.tail = CmdList(self, tail)
        self.group_id = groupId
        self.cmdKeys = cmdKeys

        self.sequence_id = None
        self.engine = None
        self.cmd = None
        self.cmdStr = None

        self.createdAt = pfsTime.Time.now()
        self.status = Status()
        self.status.onchangestate = self.genKeys

    def __str__(self):
        return f'sequence={self.sequence_id},{self.group_id},{self.seqtype},"{self.name}","{self.comments}",' \
               f'"{self.cmdStr}",{self.status}'

    @property
    def isObsolete(self):
        return (pfsTime.Time.now() - self.createdAt).value > Sequence.daysToDeclareObsolete

    @property
    def cmdList(self):
        return self.head + self

    @property
    def subCmds(self):
        return self.cmdList + self.tail

    @property
    def remainingCmds(self):
        return [subCmd for subCmd in self.cmdList if not subCmd.cmdRet.wasCalled]

    def add(self, actor, cmdStr, **kwargs):
        """ Append duplicate * subcommand to sequence """
        # instantiate subcommand.
        subCmd = self.instantiate(actor, cmdStr, **kwargs)
        # append or insert on index.
        list.append(self, subCmd)

    def append(self, *args, cmd=None, **kwargs):
        """Add subCmd and generate keys"""
        cmd = self.cmd if cmd is None else cmd
        # regular add.
        self.add(*args, **kwargs)
        # declare id and generate keys
        id = len(self.cmdList) - 1
        self[-1].init(id, cmd=cmd)

    def genKeys(self, *args, cmd=None):
        """Generate sequence keyword."""
        cmd = self.cmd if cmd is None else cmd
        cmd.inform(str(self))

    def startup(self, engine, cmd):
        """Attach engine and attach cmd"""
        self.engine = engine
        self.cmd = cmd
        # strip name and comments from rawCmd since it is redundant opdb/keyword scheme.
        self.cmdStr = makeCmdStr(cmd) if self.cmdStr is None else self.cmdStr
        # initial insert into opdb.
        self.sequence_id = opdbUtils.insertSequence(group_id=self.group_id, sequence_type=self.seqtype, name=self.name,
                                                    comments=self.comments, cmd_str=self.cmdStr)
        # declare active and generate allKeys.
        self.activate()

    def activate(self):
        """Declare sequence as active and generate sequence, subcmd keys."""
        # generate keywords for subCommand to come.
        for id, subCmd in enumerate(self.subCmds):
            subCmd.init(id, cmd=self.cmd)

        self.status.ready()

    def getNextSubCmd(self):
        """Get next subCmd in the list."""
        if not self.remainingCmds:
            return None

        return self.remainingCmds[0]

    def commandLogic(self, cmd):
        """Contain all the logic to process a sequence."""

        def cancelRemainings(cmd):
            """ Release remaining subcommand"""
            for subCmd in self.remainingCmds:
                subCmd.cancel(cmd)

        self.status.execute()

        while not self.status.isFlagged and self.getNextSubCmd():
            # get next subCommand.
            next = self.getNextSubCmd()

            # call next command, raise exception and stop here if any failure.
            try:
                next.callAndUpdate(cmd)
            except Exception as e:
                cancelRemainings(cmd)
                self.status.conclude(failure=str(e))
                raise

        # sequence could have been finished/aborted externally, so just clean the remaining ones.
        if self.remainingCmds:
            cancelRemainings(cmd)

        self.status.conclude()

        # raise SequenceAborted in that case.
        if self.status.isAborted:
            raise exception.SequenceAborted()

    def finalize(self, cmd):
        """Finalizing sequence."""
        # insert sequence_status/
        opdbUtils.insertSequenceStatus(sequence_id=self.sequence_id, status=self.status)
        # process tail, catch exception there, do not care.
        for subCmd in self.tail:
            try:
                subCmd.callAndUpdate(cmd)
            except Exception as e:
                cmd.warn(str(e))

    def doAbort(self, cmd):
        """Aborting sequence now."""
        cmd.inform(f'text="aborting sequence({self.sequence_id}) !"')
        # get current subcmd and abort.
        current = self.getNextSubCmd()
        if current:
            current.abort(cmd)

        # set flag to aborted and wait for the sequence to conclude.
        self.status.setFlag(Flag.ABORTED, doWait=True)

    def doFinish(self, cmd, now=False):
        """Finishing sequence now."""
        cmd.inform(f'text="finishing sequence({self.sequence_id}) !"')
        # get current subcmd and finish now.
        current = self.getNextSubCmd()
        if current and now:
            current.finishNow(cmd)

        # set flag to aborted and wait for the sequence to conclude.
        self.status.setFlag(Flag.FINISHNOW, doWait=True)

    def instantiate(self, actor, cmdStr, **kwargs):
        """Prototype"""
        return SubCmd(self, actor, cmdStr, **kwargs)

    def guessTimeOffset(self, subCmd):
        """Prototype"""
        return 0

    def match(self, filter):
        """do that sequence match the filter."""
        doMatch = False if filter else True
        return doMatch

    def parseGroupId(self):
        """Parse a mhs compliant argument for groupId."""
        return -1 if self.group_id is None else self.group_id


class CmdList(list):
    def __init__(self, sequence, cmdList):
        super().__init__()
        cmdList = [] if cmdList is None else cmdList

        self.sequence = sequence

        for fullCmd in cmdList:
            self.autoadd(fullCmd)

    def add(self, actor, cmdStr, **kwargs):
        """ Append duplicate * subcommand to sequence """
        # getting subCmd object
        subCmd = self.sequence.instantiate(actor, cmdStr, **kwargs)
        # append object
        self.append(subCmd)

    def autoadd(self, fullCmd):
        """ Append duplicate * subcommand to sequence """
        # simple split.
        actor, cmdStr = fullCmd.split(' ', 1)
        # getting subCmd object
        subCmd = self.sequence.instantiate(actor, cmdStr)
        # guessing timeOffset and apply
        timeOffset = self.sequence.guessTimeOffset(subCmd)
        subCmd.timeLim += timeOffset
        # just adding
        self.append(subCmd)
