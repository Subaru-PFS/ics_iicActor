from importlib import reload

import opscore.protocols.keys as keys
from ics.utils import visit


class TestCmd(object):

    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor
        seqArgs = '[<name>] [<comments>] [@doTest] [<groupId>] [<head>] [<tail>]'
        identArgs = '[<cam>] [<arm>] [<sm>]'
        commonArgs = f'{identArgs} [<duplicate>] {seqArgs}'
        timedLampsArgs = '[<hgar>] [<hgcd>] [<argon>] [<neon>] [<krypton>] [<xenon>] [@doShutterTiming]'
        windowingArgs = '[<window>] [<blueWindow>] [<redWindow>]'

        self.vocab = [
            ('testMcs1', '', self.testMcs1),
            ('reloadVisitor', '', self.reloadVisitor),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary('iic_test', (1, 1),
                                        )

    def testMcs1(self, cmd):
        """Close out the current boresight acquisition loop and process the data. """

        gen2Model = self.actor.models['gen2'].keyVarDict
        axes = gen2Model['tel_axes'].getValue()
        cmd.inform(f'text="axes={axes}"')
        cmd.finish()

    def reloadVisitor(self, cmd):
        """"""
        reload(visit)
        self.actor.engine.visitManager = visit.VisitManager(self.actor)
        cmd.finish()
