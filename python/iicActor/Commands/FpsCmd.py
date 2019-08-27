import opscore.protocols.keys as keys
import opscore.protocols.types as types
from opscore.utility.qstr import qstr

class FpsCmd(object):

    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        self.boresightLoop = None

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('startBoresightAcquisition', '', self.startBoresightAcquisition),
            ('addBoresightRotation', '', self.addBoresightRotation),
            ('reduceBoresightData', '', self.reduceBoresightData),
            ('abortBoresightAcquisition', '', self.abortBoresightAcquisition),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("iic_iic", (1, 1),
                                        )

    def startBoresightAcquisition(self, cmd):
        """Start a boresight acquisition loop. """

        if self.boresightLoop is not None:
            cmd.fail('text="boresight loop already in progress"')
            return

        cmd.finish('')

    def abortBoresightAcquisition(self, cmd):
        """Abort a boresight acquisition loop. """

        if self.boresightLoop is None:
            cmd.fail('text="no boresight loop to abort"')
            return

        cmd.finish('')

    def addBoresightPosition(self, cmd):
        """Acquire data for a new boresight position. """

        if self.boresightLoop is None:
            cmd.fail('text="no boresight loop to add to"')
            return

        cmd.finish('')

    def reduceBoresightData(self, cmd):
        """Close out the current boresight acquisition loop and process the data. """

        if self.boresightLoop is None:
            cmd.fail('text="no boresight loop to reduce"')
            return

        cmd.finish('')
