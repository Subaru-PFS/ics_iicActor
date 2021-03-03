import opscore.protocols.keys as keys
import opscore.protocols.types as types

from ics.iicActor.utils.lib import wait


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
            ('sequenceStatus', '[<id>]', self.sequenceStatus),
            ('sps', '@abortExposure [<id>]', self.abortExposure),
            ('sps', '@abort [<id>]', self.abortExposure),
            ('sps', '@finishExposure [<id>] [@noSunssBias]', self.finishExposure)
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("mcs_mcs", (1, 1),
                                        keys.Key('id', types.Int(), help='optional visit_set_id.'),
                                        )

    @property
    def resourceManager(self):
        return self.actor.resourceManager

    def sequenceStatus(self, cmd):
        cmdKeys = cmd.cmd.keywords
        visitSetId = cmdKeys['id'].values[0] if 'id' in cmdKeys else None

        self.actor.resourceManager.genStatus(cmd, visitSetId=visitSetId)
        cmd.finish()

    def abortExposure(self, cmd):
        cmdKeys = cmd.cmd.keywords
        identifier = cmdKeys['id'].values[0] if 'id' in cmdKeys else 'dcb'

        job = self.resourceManager.abort(cmd, identifier=identifier)
        while not job.isDone:
            wait()

        job.genStatus(cmd)
        cmd.finish()

    def finishExposure(self, cmd):
        cmdKeys = cmd.cmd.keywords
        identifier = cmdKeys['id'].values[0] if 'id' in cmdKeys else 'sps'
        noSunssBias = 'noSunssBias' in cmdKeys

        job = self.resourceManager.finish(cmd, identifier=identifier, noSunssBias=noSunssBias)
        while not job.isDone:
            wait()

        job.genStatus(cmd)
        cmd.finish()
