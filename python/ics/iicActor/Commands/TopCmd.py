import opscore.protocols.keys as keys
import opscore.protocols.types as types


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
            ('observe', '<designId>', self.genPfsDesignId)
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("iic_iic", (1, 1),
                                        keys.Key('designId', types.Int(), help='selected pfsDesignId')
                                        )

    def ping(self, cmd):
        """Query the actor for liveness/happiness."""

        cmd.warn("text='I am an empty and fake actor'")
        cmd.finish("text='Present and (probably) well'")

    def status(self, cmd):
        """Report camera status and actor version. """

        self.actor.sendVersionKey(cmd)
        cmd.finish()

    def genPfsDesignId(self, cmd):
        """Report camera status and actor version. """
        cmdKeys = cmd.cmd.keywords
        pfsDesignId = cmdKeys['designId'].values[0]
        cmd.finish('designId=0x%016x' % pfsDesignId)
