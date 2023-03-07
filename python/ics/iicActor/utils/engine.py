import ics.iicActor.utils.opdb as opdbUtils
from ics.utils.threading import singleShot
from ics.utils.visit import visitManager
from iicActor.utils import registry
from iicActor.utils import resourceManager


class KeyRepo(object):
    def __init__(self, engine):
        self.engine = engine

    @property
    def actor(self):
        return self.engine.actor

    def enuKeys(self, cams, keyName):
        """Get enu keys for that sequence given a key name."""
        specNames = list(set([cam.specName for cam in cams]))
        values = [self.actor.models[f'enu_{specName}'].keyVarDict[keyName].getValue() for specName in specNames]
        return dict([(specName, value) for specName, value in zip(specNames, values)])

    def hexapodPoweredOff(self, cams):
        """Return specName where the hexapod is powered off."""
        return [specName for specName, (_, state, _, _, _) in self.enuKeys(cams, 'pduPort3').items() if state == 'off']


class Engine(object):
    """ Placeholder to reject/accept incoming jobs based on the availability of the software/hardware. """

    def __init__(self, actor):
        self.actor = actor

        self.resourceManager = resourceManager.ResourceManager(actor)
        self.visitManager = visitManager.VisitManager(actor)
        self.registry = registry.Registry(self)
        self.keyRepo = KeyRepo(self)

    @singleShot
    def runInThread(self, *args, **kwargs):
        """"""
        return self.run(*args, **kwargs)

    def run(self, cmd, sequence, doFinish=True, mode='fullAuto'):
        """Main engine function.
        Note that arguments order matters, cmd is first because of how singleShot is written."""
        # make sure locked is always defined.
        locked = None
        # retrieving resources based on sequence.
        resources = self.resourceManager.inspect(sequence)
        try:
            # checking if resources are available.
            locked = self.resourceManager.request(resources)
            # processing sequence.
            if mode == 'fullAuto':
                self.fullAuto(sequence, cmd=cmd)
            elif mode == 'execute':
                self.execute(sequence, cmd=cmd)
            elif mode == 'commandOnly':
                self.commandOnly(sequence, cmd=cmd)
            else:
                raise ValueError(f'do not know this mode{mode}')

        except Exception as e:
            cmd.fail(f'text="{str(e)}"')
            return

        finally:
            self.resourceManager.free(locked)

        if doFinish:
            cmd.finish()

    def fullAuto(self, sequence, cmd):
        """Full automatic processing, insert iic_sequence, send commands and finalize, eg generate keys,
        insert iic_sequence_status...
        """
        # base insert and activate sequence.
        sequence.startup(self, cmd=cmd)

        # store in registry.
        self.registry.register(sequence)

        # start sequencing logic
        self.execute(sequence, cmd=cmd)

    def execute(self, sequence, cmd):
        """send commands and finalize."""
        sequence.cmd = cmd
        try:
            sequence.commandLogic(cmd)
        finally:
            sequence.finalize(cmd)

    def commandOnly(self, sequence, cmd):
        """Just send the available commands and generate keys."""
        sequence.cmd = cmd
        try:
            sequence.commandLogic(cmd)
        finally:
            sequence.genKeys(cmd)

    def requestGroupId(self, groupName, doContinue=False):
        """Request groupId given the groupName"""
        # find the latest one matching that name
        if doContinue:
            return opdbUtils.fetchLastGroupIdMatchingName(groupName)

        # Or just create a fresh one.
        return opdbUtils.insertSequenceGroup(groupName)

    def checkIn(self, cmd, sequence):
        """Check resources for a given sequence and do basic startup, without executing any command yet."""
        # make sure locked is always defined.
        locked = None
        # retrieving resources based on sequence.
        resources = self.resourceManager.inspect(sequence)
        try:
            # checking if resources are available.
            locked = self.resourceManager.request(resources)
            # base insert and activate sequence.
            sequence.startup(self, cmd=cmd)
            # store in registry.
            self.registry.register(sequence)

        finally:
            # I'm freeing but those will be locked in again when executing commands.
            self.resourceManager.free(locked)
