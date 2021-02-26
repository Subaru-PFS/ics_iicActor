import opscore.protocols.keys as keys
import opscore.protocols.types as types
from opscore.utility.qstr import qstr

class TopCmd(object):

    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('ping', '', self.ping),
            ('status', '', self.status),
            ('sequenceStatus', '[<id>]', self.sequenceStatus)
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("mcs_mcs", (1, 1),
                                        keys.Key('id', types.Int(), help='optional visit_set_id.'),
                                        )


    def ping(self, cmd):
        """Query the actor for liveness/happiness."""

        cmd.warn("text='I am an empty and fake actor'")
        cmd.finish("text='Present and (probably) well'")

    def status(self, cmd):
        """Report camera status and actor version. """

        self.actor.sendVersionKey(cmd)
        cmd.finish()

    def sequenceStatus(self, cmd):
        cmdKeys = cmd.cmd.keywords
        visitSetId = cmdKeys['id'].values[0] if 'id' in cmdKeys else None

        self.actor.resourceManager.getStatus(cmd, visitSetId=visitSetId)
        cmd.finish()

