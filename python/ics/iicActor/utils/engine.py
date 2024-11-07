import ics.iicActor.utils.opdb as opdbUtils
from ics.utils.threading import singleShot
from ics.utils.visit import visitManager
from iicActor.utils import keyRepo
from iicActor.utils import registry
from iicActor.utils import resourceManager


class ExecMode:
    FULLAUTO = 0  # Initialize sequence, execute command(s), and conclude.
    CHECKIN = 1  # Just initialize without executing anything.
    CONCLUDE = 2  # Execute command(s) and conclude.
    EXECUTE = 3  # Just execute command(s).


class Engine(object):
    """ Placeholder to reject/accept incoming jobs based on the availability of the software/hardware. """

    def __init__(self, actor):
        """
        Initialize the Engine with resource, visit, registry, and key repository managers.

        Parameters
        ----------
        actor : object
            The actor object responsible for handling engine operations.
        """
        self.actor = actor

        # Initialize managers for resources, visits, registry, and key repository.
        self.resourceManager = resourceManager.ResourceManager(actor)
        self.visitManager = visitManager.VisitManager(actor)
        self.registry = registry.Registry(self)
        self.keyRepo = keyRepo.KeyRepo(self)

    @singleShot
    def runInThread(self, *args, **kwargs):
        """
        Attach the run method to a QThread.

        Parameters
        ----------
        *args, **kwargs :
            Arguments to pass to the run method.
        """
        return self.run(*args, **kwargs)

    def run(self, cmd, sequence, doFinish=True, mode=ExecMode.FULLAUTO):
        """
        Main engine function to manage command execution, resource allocation, and sequence flow.

        Parameters
        ----------
        cmd : object
            The command object initiating the sequence.
        sequence : object
            Sequence object containing initialization, command logic, and finalization.
        doFinish : bool, optional
            Whether to automatically finish the command after execution, by default True.
        mode : ExecMode, optional
            Execution mode determining the sequence flow, by default ExecMode.FULLAUTO.

        Notes
        -----
        - Ensure that the argument order is maintained (cmd first) because of singleShot.
        - Defines `locked` to hold any resources locked during execution.
        """
        # Ensure locked is always defined, so resources can be freed in 'finally' block
        locked = []

        # Attach the command to the sequence by initializing it
        sequence.initialize(self, cmd)

        # Retrieve necessary resources based on the sequence requirements
        resources = self.resourceManager.inspect(sequence)
        try:
            # Attempt to lock the required resources
            locked = self.resourceManager.request(resources)

            # If mode is FULLAUTO or CHECKIN, initialize sequence and register in registry
            if mode in [ExecMode.FULLAUTO, ExecMode.CHECKIN]:
                sequence.startup()  # Run startup routine for the sequence
                self.registry.register(sequence)  # Store sequence in the registry

            # If mode is not CHECKIN, execute the command logic
            if mode != ExecMode.CHECKIN:
                try:
                    sequence.commandLogic()  # Perform main command logic
                finally:
                    # If mode is not EXECUTE, finalize the sequence
                    if mode != ExecMode.EXECUTE:
                        sequence.finalize()

        except Exception as e:
            sequence.getCmd().fail(f'text="{str(e)}"')
            return

        finally:
            self.resourceManager.free(locked)

        if doFinish:
            sequence.getCmd().finish()

    def requestGroupId(self, groupName, doContinue=False):
        """
        Request or create a sequence group ID based on the provided group name.

        Parameters
        ----------
        groupName : str
            The name of the group to retrieve or create an ID for.
        doContinue : bool, optional
            If True, fetches the last group ID matching the group name; otherwise, creates a new one.

        Returns
        -------
        int
            The group ID corresponding to the groupName.
        """
        # If doContinue is True, retrieve the latest matching group ID
        if doContinue:
            return opdbUtils.fetchLastGroupIdMatchingName(groupName)

        # Otherwise, create a new group ID for the sequence
        return opdbUtils.insertSequenceGroup(groupName)
