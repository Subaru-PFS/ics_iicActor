import ics.iicActor.utils.opdb as opdbUtils
from ics.utils.threading import singleShot
from ics.utils.visit import visitManager
from iicActor.utils import keyRepo
from iicActor.utils import registry
from iicActor.utils import resourceManager


class ExecMode:
    FULLAUTO = 0  # Initialize sequence, execute command(s) and conclude.
    CHECKIN = 1  # Just Initialize without executing anything.
    CONCLUDE = 2  # Execute command(s) and conclude.
    EXECUTE = 3  # Just execute command(s).


class Engine(object):
    """ Placeholder to reject/accept incoming jobs based on the availability of the software/hardware. """

    def __init__(self, actor):
        self.actor = actor

        self.resourceManager = resourceManager.ResourceManager(actor)
        self.visitManager = visitManager.VisitManager(actor)
        self.registry = registry.Registry(self)
        self.keyRepo = keyRepo.KeyRepo(self)

    @singleShot
    def runInThread(self, *args, **kwargs):
        """Just attach the run method to a QThread."""
        return self.run(*args, **kwargs)

    def run(self, cmd, sequence, doFinish=True, mode=ExecMode.FULLAUTO):
        """Main engine function.
        Note that arguments order matters, cmd is first because of how singleShot is written."""
        # make sure locked is always defined.
        locked = []
        # retrieving resources based on sequence.
        resources = self.resourceManager.inspect(sequence)
        try:
            # checking if resources are available.
            locked = self.resourceManager.request(resources)
            # do a startup given the mode.
            self.startup(cmd, sequence, mode=mode)
            # executing the sequence given the mode.
            self.execute(cmd, sequence, mode=mode)

        except Exception as e:
            cmd.fail(f'text="{str(e)}"')
            return

        finally:
            self.resourceManager.free(locked)

        if doFinish:
            cmd.finish()

    def startup(self, cmd, sequence, mode):
        """Sequence startup, insert iic_sequence, declare ready."""
        # no startup in that case.
        if mode not in [ExecMode.FULLAUTO, ExecMode.CHECKIN]:
            return

        # base insert and activate sequence.
        sequence.startup(self, cmd=cmd)
        # store in registry.
        self.registry.register(sequence)

    def execute(self, cmd, sequence, mode):
        """send commands and finalize if required."""
        # not executing anything in that mode.
        if mode == ExecMode.CHECKIN:
            return

        try:
            sequence.cmd = cmd
            sequence.commandLogic(cmd)
        finally:
            # not need to finalize in that mode.
            if mode != ExecMode.EXECUTE:
                sequence.finalize(cmd)

    def requestGroupId(self, groupName, doContinue=False):
        """Request groupId given the groupName"""
        # find the latest one matching that name
        if doContinue:
            return opdbUtils.fetchLastGroupIdMatchingName(groupName)

        # Or just create a fresh one.
        return opdbUtils.insertSequenceGroup(groupName)
