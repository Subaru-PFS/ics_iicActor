import ics.iicActor.utils.opdb as opdbUtils
import ics.utils.cmd as cmdUtils
import ics.utils.time as pfsTime
from ics.iicActor.utils.lib import stripQuotes
from ics.iicActor.utils.subcmd import SubCmd
from iicActor.utils import exception
from iicActor.utils import sequenceStatus

class Sequence(list):
    daysToDeclareObsolete = 7
    seqtype = 'sequence'

    def __init__(self, name="", comments="", doTest=False, head=None, tail=None, groupId=None):
        super().__init__()
        self.name = name
        self.comments = comments
        self.doTest = doTest

        self.head = CmdList(self, head)
        self.tail = CmdList(self, tail)

        self.sequence_id = None
        self.group_id = groupId

        self.engine = None
        self.cmd = None
        self.cmdStr = None

        self.createdAt = pfsTime.Time.now()
        self.status = sequenceStatus.Status.factory('init')

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

    def setStatus(self, *args, **kwargs):
        """Set status and generate sequence keyword."""
        self.status = Status.factory(*args, **kwargs)

    def genKeys(self, cmd=None):
        """Generate sequence keyword."""
        cmd = self.cmd if cmd is None else cmd
        cmd.inform(str(self))

    def startup(self, engine, cmd):
        """Attach engine and attach cmd"""
        self.engine = engine
        self.cmd = cmd
        # strip name and comments from rawCmd since it is redundant opdb/keyword scheme.
        self.cmdStr = f"iic {stripQuotes(cmdUtils.stripCmdKey(cmdUtils.stripCmdKey(cmd.rawCmd, 'name'), 'comments'))}"
        # initial insert into opdb.
        self.sequence_id = opdbUtils.insertSequence(group_id=self.group_id, sequence_type=self.seqtype, name=self.name,
                                                    comments=self.comments, cmd_str=self.cmdStr)
        # declare active and generate allKeys.
        self.activate()

    def activate(self):
        """Declare sequence as active and generate sequence, subcmd keys."""
        self.setStatus('active')
        self.genKeys()

        # generate keywords for subCommand to come.
        for id, subCmd in enumerate(self.subCmds):
            subCmd.init(id, cmd=self.cmd)

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

        while self.status.isActive:
            # get next subCommand.
            next = self.getNextSubCmd()
            # there is nothing left to do.
            if not next:
                self.setStatus('finish')
                continue

            # call next command, raise exception and stop here if any failure.
            try:
                next.callAndUpdate(cmd)
            except Exception as e:
                cancelRemainings(cmd)
                self.setStatus('fail', output=str(e))
                raise

        # sequence could have been finished/aborted externally, so just clean the remaining ones.
        if self.remainingCmds:
            cancelRemainings(cmd)

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

        self.genKeys(cmd)

    def doAbort(self, cmd):
        """Aborting sequence now."""
        cmd.inform(f'text="aborting sequence({self.sequence_id}) !"')
        # get current subcmd and abort.
        current = self.getNextSubCmd()
        if current:
            current.abort(cmd)

        self.setStatus('abort')

    def doFinish(self, cmd, now=False):
        """Finishing sequence now."""
        cmd.inform(f'text="finishing sequence({self.sequence_id}) !"')
        # get current subcmd and finish now.
        current = self.getNextSubCmd()
        if current and now:
            current.finishNow(cmd)

        self.setStatus('finishNow')

    def instantiate(self, actor, cmdStr, **kwargs):
        """Prototype"""
        return SubCmd(self, actor, cmdStr, **kwargs)

    def guessTimeOffset(self, subCmd):
        """Prototype"""
        return 0


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
