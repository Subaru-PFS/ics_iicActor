import ics.iicActor.utils.lib as iicUtils
import ics.iicActor.sps.sequenceList as spsSequence
import opscore.protocols.keys as keys
import opscore.protocols.types as types


class SuNSSCmd(object):

    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        identArgs = '[<cam>] [<arm>] [<sm>]'
        self.vocab = [
            ('sps', f'@startExposures <exptime> {identArgs} [<name>] [<comments>] [@doBias] [@doTest]', self.startExposures),
            ('domeFlat', f'<exptime> {identArgs} [<name>] [<comments>] [<duplicate>] [@doTest]', self.domeFlat),
            ('domeArc', f'<exptime> {identArgs} [<name>] [<comments>] [<duplicate>] [@doTest]', self.domeArc),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary('iic_sunss', (1, 1),
                                        keys.Key('exptime', types.Float() * (1,), help='exptime list (seconds)'),
                                        keys.Key('cam', types.String() * (1,), help='camera(s) to take exposure from'),
                                        keys.Key('arm', types.String() * (1,), help='arm to take exposure from'),
                                        keys.Key('sm', types.Int() * (1,),
                                                 help='spectrograph module(s) to take exposure from'),
                                        keys.Key('name', types.String(), help='iic_sequence name'),
                                        keys.Key('comments', types.String(), help='iic_sequence comments'),
                                        keys.Key('duplicate', types.Int(), help='exposure duplicate (1 is default)'),
                                        )

    @property
    def resourceManager(self):
        return self.actor.resourceManager

    def domeFlat(self, cmd):
        cmdKeys = cmd.cmd.keywords

        seqKwargs = iicUtils.genSequenceKwargs(cmd, customMade=False)
        exptime = cmdKeys['exptime'].values
        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1

        job = self.resourceManager.request(cmd, spsSequence.DomeFlat)
        job.instantiate(cmd, exptime=exptime, duplicate=duplicate, **seqKwargs)

        job.fire(cmd)

    def domeArc(self, cmd):
        cmdKeys = cmd.cmd.keywords

        seqKwargs = iicUtils.genSequenceKwargs(cmd, customMade=False)
        exptime = cmdKeys['exptime'].values
        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1

        job = self.resourceManager.request(cmd, spsSequence.DomeArc)
        job.instantiate(cmd, exptime=exptime, duplicate=duplicate, **seqKwargs)

        job.fire(cmd)

    def startExposures(self, cmd):
        cmdKeys = cmd.cmd.keywords

        seqKwargs = iicUtils.genSequenceKwargs(cmd, customMade=False)
        exptime = cmdKeys['exptime'].values[0]
        objectLoop = spsSequence.ObjectInterleavedBiasLoop if 'doBias' in cmdKeys else spsSequence.ObjectLoop

        job = self.resourceManager.request(cmd, objectLoop)
        job.instantiate(cmd, exptime=exptime, **seqKwargs)

        cmd.finish()
        job.fire(cmd=self.actor.bcast)
