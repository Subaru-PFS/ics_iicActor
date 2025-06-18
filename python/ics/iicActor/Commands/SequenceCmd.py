import opscore.protocols.keys as keys
import opscore.protocols.types as types
from opscore.utility.qstr import qstr
import ics.utils.time as pfsTime
from ics.utils.threading import singleShot
from iicActor.utils import exception

class SequenceCmd(object):

    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('sequence', '@abort [<id>]', self.abortSequence),
            ('sequence', '@finish [<id>] [@(now)]', self.finishSequence),
            ('sequence', '@continue <id>', self.restartSequence),
            ('sequence', '@copy <id>', self.restartSequence),
            ('sps', '@abortExposure [<id>] [@(sunss)]', self.abortSpsExposure),
            ('sps', '@finishExposure [@(now)] [<id>] [@(sunss)]', self.finishSpsExposure),
            ('sps', 'waitForSequenceCompletion [<id>]', self.waitForSequenceCompletion),

            ('getGroupId', '<groupName> [(@continue)]', self.getGroupId)
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("iic_sequence", (1, 1),
                                        keys.Key('id', types.Int(), help='optional sequence_id.'),
                                        keys.Key('groupName', types.String(), help='group identifier'),
                                        )

    @property
    def engine(self):
        return self.actor.engine

    @singleShot
    def abortSequence(self, cmd):
        """
        `iic sequence abort id=N`

        abort iic sequence.

        Parameters
        ---------
        id : `int`
           optional sequenceId.
        """
        try:
            sequence = self.engine.registry.identify(cmd.cmd.keywords)
            sequence.doAbort(cmd)
        except Exception as e:
            cmd.fail(f'text="{str(e)}"')
            return

        cmd.finish()

    @singleShot
    def finishSequence(self, cmd):
        """
        `iic sequence finish id=N`

        finish iic sequence.

        Parameters
        ---------
        id : `int`
           optional sequenceId.
        """
        cmdKeys = cmd.cmd.keywords
        now = 'now' in cmdKeys
        try:
            sequence = self.engine.registry.identify(cmdKeys)
            sequence.doFinish(cmd, now=now)
        except Exception as e:
            cmd.fail(f'text="{str(e)}"')
            return

        cmd.finish()

    def restartSequence(self, cmd):
        """
        `iic sequence continue id=N`

        continue/copy an iic sequence.

        Parameters
        ---------
        id : `int`
           optional sequenceId.
        """
        cmdKeys = cmd.cmd.keywords
        sequenceId = int(cmdKeys['id'].values[0])

        try:
            sequence = self.engine.registry[sequenceId]
        except KeyError:
            raise RuntimeError(f'could not find sequence with sequenceId=={sequenceId}')

        # make a copy using the saved cmdKeys and set the same cmdStr as the original.
        copy = sequence.fromCmdKeys(self.actor, sequence.cmdKeys)
        copy.cmdStr = sequence.cmdStr

        if 'continue' in cmdKeys:
            # indicate that this sequence is an extension.
            copy.seqtype = f'{copy.seqtype}_continued'
            copy.comments = f'continue {sequenceId}'

            # do not re-execute already successful subcommands.
            for i in range(len(sequence.cmdList)):
                if sequence.cmdList[i].cmdRet.succeed:
                    copy.cmdList[i].cmdRet.status = 0

        self.engine.runInThread(cmd, copy)

    @singleShot
    def abortSpsExposure(self, cmd):
        """
        `iic sps @abort [id=N]`

        abort current sps exposure.

        Parameters
        ---------
        id : `int`
           optional sequenceId.
        """
        cmdKeys = cmd.cmd.keywords
        filter = 'sunss' if 'sunss' in cmdKeys else 'sps'

        try:
            sequence = self.engine.registry.identify(cmdKeys, filter=filter)
            sequence.doAbort(cmd)
        except Exception as e:
            cmd.fail(f'text="{str(e)}"')
            return

        sequence.waitWhileAlive(timeout=1)
        cmd.finish()

    @singleShot
    def finishSpsExposure(self, cmd):
        """
        `iic sps @finishExposure [now] [id=N]`

        finish current sps exposure.

        Parameters
        ---------
        id : `int`
           optional sequenceId.
        """
        cmdKeys = cmd.cmd.keywords
        now = 'now' in cmdKeys
        filter = 'sunss' if 'sunss' in cmdKeys else 'sps'

        try:
            sequence = self.engine.registry.identify(cmdKeys, filter=filter)
            sequence.doFinish(cmd, now=now)
        except Exception as e:
            cmd.fail(f'text="{str(e)}"')
            return

        sequence.waitWhileAlive(timeout=1)
        cmd.finish()

    @singleShot
    def getGroupId(self, cmd):
        """
        `iic getGroupId [continue]`

        Get new groupId or current if continue.

        Parameters
        ---------
        id : `int`
           optional sequenceId.
        """
        cmdKeys = cmd.cmd.keywords
        doContinue = 'continue' in cmdKeys
        groupName = cmdKeys['groupName'].values[0]

        try:
            groupId = self.engine.requestGroupId(groupName, doContinue=doContinue)
        except Exception as e:
            cmd.fail(f'text="{str(e)}"')
            return

        cmd.finish(f'groupId={groupId},{qstr(groupName)}')

    @singleShot
    def waitForSequenceCompletion(self, cmd):
        """Find the sequence running in background and wait for completion."""
        cmdKeys = cmd.cmd.keywords

        try:
            # identifying the sequence running in background.
            sequence = self.engine.registry.identify(cmdKeys, filter='returnWhenShutterClose')
        except exception.SequenceIdentificationFailure:
            cmd.finish('text="could not identify sequence with returnWhenShutterClose set, finishing now..."')
            return

        start = pfsTime.timestamp()

        while not sequence.cmd is None:
            if pfsTime.timestamp() - start > sequence.timeLim:
                raise RuntimeError(f'Sequence did not return when shutter close after {sequence.timeLim} s')

            pfsTime.sleep.millisec()

        # attaching the command to the active sequence.
        sequence.setCmd(cmd)
