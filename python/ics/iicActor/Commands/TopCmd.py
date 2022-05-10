import opscore.protocols.keys as keys
import opscore.protocols.types as types
from pfs.datamodel import PfsDesign


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
            ('declareCurrentPfsDesign', '<designId>', self.declareCurrentPfsDesign),
            ('finishField', '', self.finishField)
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("iic_iic", (1, 1),
                                        keys.Key('designId', types.Long(), help='selected pfsDesignId')
                                        )

    def ping(self, cmd):
        """Query the actor for liveness/happiness."""

        cmd.warn("text='I am an empty and fake actor'")
        cmd.finish("text='Present and (probably) well'")

    def status(self, cmd):
        """Report camera status and actor version. """

        self.actor.sendVersionKey(cmd)
        cmd.finish()

    def declareCurrentPfsDesign(self, cmd):
        """Report camera status and actor version. """
        cmdKeys = cmd.cmd.keywords
        pfsDesignId = cmdKeys['designId'].values[0]
        # opening pfsDesignFile
        pfsDesign = PfsDesign.read(pfsDesignId, dirName=self.actor.actorConfig['pfsDesign']['root'])
        # declaring new field
        visit0 = self.actor.visitor.declareNewField(designId=pfsDesignId)
        # generating keyword for gen2
        cmd.finish('pfsDesign=0x%016x,%d,%.6f,%.6f,%.6f,%s' % (pfsDesignId,
                                                               visit0.visitId,
                                                               pfsDesign.raBoresight,
                                                               pfsDesign.decBoresight,
                                                               pfsDesign.posAng,
                                                               pfsDesign.designName))

    def finishField(self, cmd):
        """Report camera status and actor version. """
        self.actor.visitor.finishField()

        cmd.finish()
