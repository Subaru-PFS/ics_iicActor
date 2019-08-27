import opscore.protocols.keys as keys
import opscore.protocols.types as types
from opscore.utility.qstr import qstr

class TestCmd(object):

    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        self.vocab = [
            ('testMcs1', '', self.testMcs1),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("iic_test", (1, 1),
                                        )

    def testMcs1(self, cmd):
        """Close out the current boresight acquisition loop and process the data. """

        gen2Model = self.actor.models['gen2'].keyVarDict
        axes = gen2Model['tel_axes'].getValue()
        cmd.inform(f'text="axes={axes}"')
        cmd.finish('')
