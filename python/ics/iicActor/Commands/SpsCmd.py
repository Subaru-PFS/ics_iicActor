from importlib import reload

import ics.iicActor.sps as spsSequence
import numpy as np
import opscore.protocols.keys as keys
import opscore.protocols.types as types
from ics.iicActor.utils import singleShot


reload(spsSequence)


def cmdKwargs(cmdKeys):
    duplicate = cmdKeys['duplicate'].values[0] if "duplicate" in cmdKeys else 1
    cams = ','.join(cmdKeys['cam'].values) if 'cam' in cmdKeys else None
    name = cmdKeys['name'].values[0] if 'name' in cmdKeys else ''
    comments = cmdKeys['comments'].values[0] if 'comments' in cmdKeys else ''
    head = cmdKeys['head'].values if 'head' in cmdKeys else None
    tail = cmdKeys['tail'].values if 'tail' in cmdKeys else None
    return dict(duplicate=duplicate, cams=cams, name=name, comments=comments, head=head, tail=tail)


def dcbKwargs(cmdKeys):
    switchOn = ','.join(cmdKeys['switchOn'].values) if 'switchOn' in cmdKeys else None
    switchOff = ','.join(cmdKeys['switchOff'].values) if 'switchOff' in cmdKeys else None
    switchOff = 'halogen' if not switchOff and switchOff is not None else switchOff
    doWarmup = 'switchOn' in cmdKeys or 'iisOn' not in cmdKeys
    warmingTime = cmdKeys['warmingTime'].values[0] if ('warmingTime' in cmdKeys and doWarmup) else None
    value = cmdKeys['attenuator'].values[0] if 'attenuator' in cmdKeys else None
    force = 'force' in cmdKeys

    timeLim = 60 if value is not None else None
    timeLim = 180 if switchOn is not None else timeLim
    timeLim = (warmingTime + 30) if warmingTime is not None else timeLim

    dcbOn = dict(on=switchOn, warmingTime=warmingTime, attenuator=value, force=force, timeLim=timeLim)
    dcbOff = dict(off=switchOff)

    return dcbOn, dcbOff


def iisKwargs(cmdKeys):
    switchOn = ','.join(cmdKeys['iisOn'].values) if 'iisOn' in cmdKeys else None
    switchOff = ','.join(cmdKeys['iisOff'].values) if 'iisOff' in cmdKeys else None
    doWarmup = 'iisOn' in cmdKeys or 'switchOn' not in cmdKeys
    warmingTime = cmdKeys['warmingTime'].values[0] if ('warmingTime' in cmdKeys and doWarmup) else None
    timeLim = 90 if switchOn is not None else None
    timeLim = (warmingTime + 30) if warmingTime is not None else timeLim

    iisOn = dict(on=switchOn, warmingTime=warmingTime, timeLim=timeLim)
    iisOff = dict(off=switchOff)

    return iisOn, iisOff


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
        dcbArgs = f'[<switchOn>] [<switchOff>] [<warmingTime>] [<attenuator>] [force]'
        iisArgs = f'[<iisOn>] [<iisOff>]'
        self.vocab = [
            ('expose', f'[object] <exptime> {optArgs}', self.doExpose),
            ('bias', f'{optArgs}', self.doBias),
            ('dark', f'<exptime> {optArgs}', self.doDark),
            ('expose', f'arc <exptime> {dcbArgs} {iisArgs} {optArgs}', self.doArc),
            ('expose', f'flat <exptime> [switchOff] {dcbArgs} {optArgs}', self.doFlat),
            ('slit', f'throughfocus <exptime> <position> {dcbArgs} {optArgs}', self.slitThroughFocus),
            ('detector', f'throughfocus <exptime> <position> [<tilt>] {dcbArgs} {optArgs}', self.detThroughFocus),
            ('dither', f'flat <exptime> <pixels> [<nPositions>] [switchOff] {dcbArgs} {optArgs}', self.ditheredFlats),
            ('dither', f'arc <exptime> <pixels> [doMinus] {dcbArgs} {optArgs}', self.ditheredArcs),
            ('defocus', f'arc <exptime> <position> {dcbArgs} {optArgs}', self.defocus),
            ('custom', '[<name>] [<comments>] [<head>] [<tail>]', self.custom),
            ('sps', 'abort', self.abort)

        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary('iic_iic', (1, 1),
                                        keys.Key('exptime', types.Float() * (1,), help='exptime list (seconds)'),
                                        keys.Key('duplicate', types.Int(), help='exposure duplicate (1 is default)'),
                                        keys.Key('cam', types.String() * (1,), help='camera(s) to take exposure from'),
                                        keys.Key('name', types.String(), help='sps_sequence name'),
                                        keys.Key('comments', types.String(), help='sps_sequence comments'),
                                        keys.Key('head', types.String() * (1,), help='cmdStr list to process before'),
                                        keys.Key('tail', types.String() * (1,), help='cmdStr list to process after'),
                                        keys.Key('switchOn', types.String() * (1, None),
                                                 help='which dcb lamp to switch on.'),
                                        keys.Key('switchOff', types.String() * (1, None),
                                                 help='which dcb lamp to switch off.'),
                                        keys.Key('iisOn', types.String() * (1, None),
                                                 help='which iis lamp to switch on.'),
                                        keys.Key('iisOff', types.String() * (1, None),
                                                 help='which iis lamp to switch off.'),
                                        keys.Key('attenuator', types.Int(), help='Attenuator value.'),
                                        keys.Key('position', types.Float() * (1, 3),
                                                 help='slit/motor position for throughfocus same args as np.linspace'),
                                        keys.Key('tilt', types.Float() * (1, 3), help='motor tilt (a, b, c)'),
                                        keys.Key('nPositions', types.Int(),
                                                 help='Number of position for dithered flats (default : 20)'),
                                        keys.Key('pixels', types.Float(), help='dithering step in pixels'),
                                        keys.Key('warmingTime', types.Float(), help='customizable warming time'),
                                        )

    def doExpose(self, cmd):
        """sps exposure with given exptime. """
        cmdKeys = cmd.cmd.keywords
        exptime = cmdKeys['exptime'].values

        seq = spsSequence.Object(exptime=exptime, **cmdKwargs(cmdKeys))
        self.process(cmd, seq=seq)

    def doBias(self, cmd):
        """sps bias(es). """
        cmdKeys = cmd.cmd.keywords

        seq = spsSequence.Bias(**cmdKwargs(cmdKeys))
        self.process(cmd, seq=seq)

    def doDark(self, cmd):
        """sps dark(s) with given exptime. """
        cmdKeys = cmd.cmd.keywords
        exptime = cmdKeys['exptime'].values

        seq = spsSequence.Dark(exptime=exptime, **cmdKwargs(cmdKeys))
        self.process(cmd, seq=seq)

    def doArc(self, cmd):
        """sps arc(s) with given exptime. """
        cmdKeys = cmd.cmd.keywords
        dcbOn, dcbOff = dcbKwargs(cmdKeys)

        if dcbOn['attenuator'] is not None and self.actor.site != 'L':
            raise ValueError('You can only set attenuator at LAM')

        iisOn, iisOff = iisKwargs(cmdKeys)
        exptime = cmdKeys['exptime'].values

        seq = spsSequence.Arc(exptime=exptime, dcbOn=dcbOn, dcbOff=dcbOff, iisOn=iisOn, iisOff=iisOff,
                              **cmdKwargs(cmdKeys))
        self.process(cmd, seq=seq)

    def doFlat(self, cmd):
        """sps flat(s), also known as fiberTrace, with given exptime. """
        cmdKeys = cmd.cmd.keywords
        dcbOn, dcbOff = dcbKwargs(cmdKeys)

        if dcbOn['attenuator'] is not None and self.actor.site != 'L':
            raise ValueError('You can only set attenuator at LAM')

        dcbOn['on'] = 'halogen'
        exptime = cmdKeys['exptime'].values

        seq = spsSequence.Flat(exptime=exptime, dcbOn=dcbOn, dcbOff=dcbOff, **cmdKwargs(cmdKeys))
        self.process(cmd, seq=seq)

    def slitThroughFocus(self, cmd):
        """sps slit through focus with given exptime. """
        cmdKeys = cmd.cmd.keywords
        dcbOn, dcbOff = dcbKwargs(cmdKeys)

        if dcbOn['attenuator'] is not None and self.actor.site != 'L':
            raise ValueError('You can only set attenuator at LAM')

        exptime = cmdKeys['exptime'].values
        start, stop, num = cmdKeys['position'].values
        positions = np.linspace(start, stop, num=int(num))

        seq = spsSequence.SlitThroughFocus(exptime=exptime, positions=positions.round(6), dcbOn=dcbOn, dcbOff=dcbOff,
                                           **cmdKwargs(cmdKeys))
        self.process(cmd, seq=seq)

    def detThroughFocus(self, cmd):
        """sps detector motors through focus with given exptime. """
        cmdKeys = cmd.cmd.keywords
        dcbOn, dcbOff = dcbKwargs(cmdKeys)

        if dcbOn['attenuator'] is not None and self.actor.site != 'L':
            raise ValueError('You can only set attenuator at LAM')

        exptime = cmdKeys['exptime'].values
        start, stop, num = cmdKeys['position'].values
        tilt = np.array(cmdKeys['tilt'].values) if 'tilt' in cmdKeys else np.zeros(3)
        positions = np.array([np.linspace(start, stop - np.max(tilt), num=int(num)), ] * 3).transpose() + tilt

        seq = spsSequence.DetThroughFocus(exptime=exptime, positions=positions.round(2), dcbOn=dcbOn, dcbOff=dcbOff,
                                          **cmdKwargs(cmdKeys))
        self.process(cmd, seq=seq)

    def ditheredFlats(self, cmd):
        """dithered flat(fiberTrace) with given exptime. Used to construct masterFlat """
        cmdKeys = cmd.cmd.keywords
        dcbOn, dcbOff = dcbKwargs(cmdKeys)

        if dcbOn['attenuator'] is not None and self.actor.site != 'L':
            raise ValueError('You can only set attenuator at LAM')

        dcbOn['on'] = 'halogen'
        exptime = cmdKeys['exptime'].values
        pixels = cmdKeys['pixels'].values[0]
        nPositions = cmdKeys['nPositions'].values[0] if 'nPositions' in cmdKeys else 20
        nPositions = (nPositions // 2) * 2
        positions = np.linspace(-nPositions * pixels, nPositions * pixels, 2 * nPositions + 1)

        seq = spsSequence.DitheredFlats(exptime=exptime, positions=positions.round(5), dcbOn=dcbOn, dcbOff=dcbOff,
                                        **cmdKwargs(cmdKeys))
        self.process(cmd, seq=seq)

    def ditheredArcs(self, cmd):
        """dithered Arc(s) with given exptime. """
        cmdKeys = cmd.cmd.keywords
        dcbOn, dcbOff = dcbKwargs(cmdKeys)

        if dcbOn['attenuator'] is not None and self.actor.site != 'L':
            raise ValueError('You can only set attenuator at LAM')

        exptime = cmdKeys['exptime'].values
        pixels = cmdKeys['pixels'].values[0]
        doMinus = 'doMinus' in cmdKeys

        seq = spsSequence.DitheredArcs(exptime=exptime, pixels=pixels, doMinus=doMinus, dcbOn=dcbOn, dcbOff=dcbOff,
                                       **cmdKwargs(cmdKeys))
        self.process(cmd, seq=seq)

    def defocus(self, cmd):
        """dithered Arc(s) with given exptime. """
        cmdKeys = cmd.cmd.keywords
        dcbOn, dcbOff = dcbKwargs(cmdKeys)

        if dcbOn['attenuator'] is not None and self.actor.site != 'L':
            raise ValueError('You can only set attenuator at LAM')

        exptime = cmdKeys['exptime'].values
        start, stop, num = cmdKeys['position'].values
        positions = np.linspace(start, stop, num=int(num))

        seq = spsSequence.Defocus(exp_time_0=exptime, positions=positions.round(6), dcbOn=dcbOn, dcbOff=dcbOff,
                                  **cmdKwargs(cmdKeys))
        self.process(cmd, seq=seq)

    def custom(self, cmd):
        """dithered Arc(s) with given exptime. """
        cmdKeys = cmd.cmd.keywords

        seq = spsSequence.Custom(**cmdKwargs(cmdKeys))
        self.process(cmd, seq=seq)

    @singleShot
    def process(self, cmd, seq):
        """Process sequence in another thread """
        if self.seq is not None:
            cmd.fail('text="sequence already ongoing"')
            return

        self.seq = seq
        try:
            self.seq.start(self.actor, cmd=cmd)
        finally:
            self.seq = None

        cmd.finish()

    def abort(self, cmd):
        """Abort current sequence."""
        if self.seq is None:
            cmd.fail('text="no sequence to abort"')
            return

        self.seq.abort(cmd)
        cmd.finish()
