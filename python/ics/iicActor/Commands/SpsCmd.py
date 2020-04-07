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
            ('dark', f'<exptime> {optArgs}', self.doDark),
            ('expose', f'arc <exptime> [<switchOn>] [<switchOff>] [<attenuator>] [force] {optArgs}', self.doArc),
            ('expose', f'flat <exptime> [switchOff] [<attenuator>] [force] {optArgs}', self.doFlat),

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
                                        keys.Key("switchOn", types.String() * (1, None),
                                                 help='which arc lamp to switch on.'),
                                        keys.Key("switchOff", types.String() * (1, None),
                                                 help='which arc lamp to switch off.'),
                                        keys.Key("attenuator", types.Int(), help='Attenuator value.'),
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
        """sps bias(es). """
        cmdKeys = cmd.cmd.keywords

        self.seq = spsSequence.Bias(**cmdKwargs(cmdKeys))
        try:
            self.seq.start(self.actor, cmd=cmd)
        finally:
            self.seq = None

        cmd.finish()

    def doDark(self, cmd):
        """sps dark(s) with given exptime. """
        cmdKeys = cmd.cmd.keywords
        exptime = cmdKeys['exptime'].values[0]

        self.seq = spsSequence.Dark(exptime=exptime, **cmdKwargs(cmdKeys))
        try:
            self.seq.start(self.actor, cmd=cmd)
        finally:
            self.seq = None

        cmd.finish()

    def doArc(self, cmd):
        """sps arc(s) with given exptime. """
        cmdKeys = cmd.cmd.keywords
        exptime = cmdKeys['exptime'].values[0]
        switchOn = cmdKeys['switchOn'].values if 'switchOn' in cmdKeys else None
        switchOff = cmdKeys['switchOff'].values if 'switchOff' in cmdKeys else None
        attenuator = cmdKeys['attenuator'].values[0] if 'attenuator' in cmdKeys else None
        force = 'force' in cmdKeys

        self.seq = spsSequence.Arc(exptime=exptime, switchOn=switchOn, switchOff=switchOff, attenuator=attenuator,
                                   force=force, **cmdKwargs(cmdKeys))
        try:
            self.seq.start(self.actor, cmd=cmd)
        finally:
            self.seq = None

        cmd.finish()

    def doFlat(self, cmd):
        """sps flat(s) with given exptime. """
        cmdKeys = cmd.cmd.keywords
        exptime = cmdKeys['exptime'].values[0]

        switchOff = 'switchOff' in cmdKeys
        attenuator = cmdKeys['attenuator'].values[0] if 'attenuator' in cmdKeys else None
        force = 'force' in cmdKeys

        self.seq = spsSequence.Flat(exptime=exptime, switchOff=switchOff, attenuator=attenuator,
                                    force=force, **cmdKwargs(cmdKeys))
        try:
            self.seq.start(self.actor, cmd=cmd)
        finally:
            self.seq = None

        cmd.finish()
