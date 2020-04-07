from importlib import reload

import ics.iicActor.sps as spsSequence
import opscore.protocols.keys as keys
import opscore.protocols.types as types

reload(spsSequence)

def cmdKwargs(cmdKeys):
    duplicate = cmdKeys['duplicate'].values[0] if "duplicate" in cmdKeys else 1
    cams = 'cams=%s' % ','.join(cmdKeys['cam'].values) if 'cam' in cmdKeys else ''
    name = cmdKeys['name'].values[0] if 'name' in cmdKeys else ''
    comments = cmdKeys['comments'].values[0] if 'comments' in cmdKeys else ''
    head = cmdKeys['head'].values if 'head' in cmdKeys else None
    tail = cmdKeys['tail'].values if 'tail' in cmdKeys else None
    return dict(duplicate=duplicate, cams=cams, name=name, comments=comments, head=head, tail=tail)

class SpsCmd(object):

    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor
        self.seq = None

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        optArgs = '[<duplicate>] [<cam>] [<name>] [<comments>] [<head>] [<tail>]'

        self.vocab = [
            ('expose', f'<exptime> {optArgs}', self.doExpose),
            ('bias', f'{optArgs}', self.doBias),

            ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("iic_iic", (1, 1),
                                        keys.Key("exptime", types.Float(), help="Seconds for exposure"),
                                        keys.Key("duplicate", types.Int(), help="exposure duplicate (1 is default)"),
                                        keys.Key("cam", types.String() * (1,), help='camera(s) to take exposure from'),
                                        keys.Key("name", types.String(), help='sps_sequence name'),
                                        keys.Key("comments", types.String(), help='sps_sequence comments'),
                                        keys.Key("head", types.String() * (1,), help='cmdStr list to process before'),
                                        keys.Key("tail", types.String() * (1,), help='cmdStr list to process after'),
                                        )

    def doExpose(self, cmd):
        """sps exposure with given exptime. """
        cmdKeys = cmd.cmd.keywords
        exptime = cmdKeys['exptime'].values[0]

        self.seq = spsSequence.Object(exptime=exptime, **cmdKwargs(cmdKeys))
        try:
            self.seq.start(self.actor, cmd=cmd)
        finally:
            self.seq = None

        cmd.finish()

    def doBias(self, cmd):
        """sps biases. """
        cmdKeys = cmd.cmd.keywords

        self.seq = spsSequence.Bias(**cmdKwargs(cmdKeys))
        try:
            self.seq.start(self.actor, cmd=cmd)
        finally:
            self.seq = None

        cmd.finish()
