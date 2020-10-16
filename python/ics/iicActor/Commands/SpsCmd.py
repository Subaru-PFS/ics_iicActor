from importlib import reload

import ics.iicActor.sps as spsSequence
import ics.iicActor.sps.timed as timedSpsSequence
import numpy as np
import opscore.protocols.keys as keys
import opscore.protocols.types as types
from ics.iicActor.utils import singleShot

reload(spsSequence)
reload(timedSpsSequence)


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


def timedDcbKwargs(cmdKeys):
    lampNames = 'halogen', 'hgar', 'argon', 'neon', 'krypton'
    dcbPrepare = {name: cmdKeys[name].values[0] for name in lampNames if name in cmdKeys}

    return dcbPrepare


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


def safeKwargs(cmd, head=None, tail=None, **kwargs):
    if not (head is None and tail is None):
        cmd.warn('text="not parsing head or tail here, sorry...')

    kwargs['head'] = None
    kwargs['tail'] = None

    return kwargs


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
        timedDcbArcArgs = '[<hgar>] [<argon>] [<neon>] [<krypton>]'
        iisArgs = f'[<iisOn>] [<iisOff>]'
        self.vocab = [
            ('masterBiases', f'{optArgs}', self.masterBiases),
            ('masterDarks', f'[<exptime>] {optArgs}', self.masterDarks),
            ('ditheredFlats', f'<exptime> [<pixels>] [<nPositions>] [switchOff] {dcbArgs} {optArgs}',self.ditheredFlats),
            ('scienceArc', f'<exptime> {dcbArgs} {optArgs}', self.scienceArc),
            ('scienceTrace', f'<exptime> [switchOff] {dcbArgs} {optArgs}', self.scienceTrace),
            ('scienceObject', f'<exptime> {optArgs}', self.scienceObject),
            ('bias', f'{optArgs}', self.doBias),
            ('dark', f'<exptime> {optArgs}', self.doDark),
            ('expose', f'arc <exptime> {dcbArgs} {iisArgs} {optArgs}', self.doArc),
            ('expose', f'flat <exptime> [switchOff] {dcbArgs} {optArgs}', self.doFlat),
            ('expose', f'[object] <exptime> {optArgs}', self.doExpose),
            ('slit', f'throughfocus <exptime> <position> {dcbArgs} {optArgs}', self.slitThroughFocus),
            ('detector', f'throughfocus <exptime> <position> [<tilt>] {dcbArgs} {optArgs}', self.detThroughFocus),
            ('dither', f'arc <exptime> <pixels> [doMinus] {dcbArgs} {optArgs}', self.ditheredArcs),
            ('defocus', f'arc <exptime> <position> {dcbArgs} {optArgs}', self.defocus),
            ('custom', '[<name>] [<comments>] [<head>] [<tail>]', self.custom),
            ('sps', 'abort', self.abort),

            ('ditheredFlats', f'<halogen> [<pixels>] [<nPositions>] {optArgs}', self.doTimedDitheredFlats),
            ('expose', f'arc {timedDcbArcArgs} {optArgs}', self.doTimedArc),
            ('expose', f'flat <halogen> {optArgs}', self.doTimedFlat),
            ('test', f'hexapodStability {timedDcbArcArgs} [<position>] {optArgs}', self.hexapodStability),
            ('dither', f'arc {timedDcbArcArgs} <pixels> [doMinus] {optArgs}', self.doTimedDitheredArcs),
            ('detector', f'throughfocus {timedDcbArcArgs} <position> [<tilt>] {optArgs}', self.doTimedDetThroughFocus),

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
                                        keys.Key('halogen', types.Float(), help='quartz halogen lamp on time'),
                                        keys.Key('argon', types.Float(), help='Ar lamp on time'),
                                        keys.Key('hgar', types.Float(), help='HgAr lamp on time'),
                                        keys.Key('neon', types.Float(), help='Ne lamp on time'),
                                        keys.Key('krypton', types.Float(), help='Kr lamp on time'),
                                        )

    def sanityCheck(self, cmd, cams=None, **kwargs):
        cams = f'cams={cams}' if cams is not None else ''
        ret = self.actor.cmdr.call(actor='sps', cmdStr=f'checkFocus {cams}', forUserCmd=cmd, timeLim=10)

        if ret.didFail:
            for reply in ret.replyList:
                cmd.warn(reply.keywords.canonical(delimiter=';'))
            return False

        return True

    def masterBiases(self, cmd):
        """sps bias(es). """
        cmdKeys = cmd.cmd.keywords
        kwargs = safeKwargs(cmd, **cmdKwargs(cmdKeys))
        kwargs['duplicate'] = max(kwargs['duplicate'], 15)
        kwargs['name'] = 'calibrationData' if not kwargs['name'] else kwargs['name']

        seq = spsSequence.Bias(seqtype='masterBiases', **kwargs)
        self.process(cmd, seq=seq)

    def masterDarks(self, cmd):
        """sps dark(s) with given exptime. """
        cmdKeys = cmd.cmd.keywords
        kwargs = safeKwargs(cmd, **cmdKwargs(cmdKeys))
        kwargs['duplicate'] = max(kwargs['duplicate'], 15)
        kwargs['name'] = 'calibrationData' if not kwargs['name'] else kwargs['name']
        exptime = cmdKeys['exptime'].values if 'exptime' in cmdKeys else [300]

        seq = spsSequence.Dark(seqtype='masterDarks', exptime=exptime, **kwargs)
        self.process(cmd, seq=seq)

    def ditheredFlats(self, cmd):
        """dithered flat(fiberTrace) with given exptime. Used to construct masterFlat """
        cmdKeys = cmd.cmd.keywords
        dcbOn, dcbOff = dcbKwargs(cmdKeys)
        kwargs = safeKwargs(cmd, **cmdKwargs(cmdKeys))

        if not self.sanityCheck(cmd, **kwargs):
            cmd.fail('text="sanityCheck has failed')
            return

        if dcbOn['attenuator'] is not None and self.actor.site != 'L':
            raise ValueError('You can only set attenuator at LAM')

        dcbOn['on'] = 'halogen'
        exptime = cmdKeys['exptime'].values
        pixels = cmdKeys['pixels'].values[0] if 'pixels' in cmdKeys else 0.3
        nPositions = cmdKeys['nPositions'].values[0] if 'nPositions' in cmdKeys else 20
        nPositions = (nPositions // 2) * 2
        positions = np.linspace(-nPositions * pixels, nPositions * pixels, 2 * nPositions + 1)
        kwargs['name'] = 'calibrationData' if not kwargs['name'] else kwargs['name']

        seq = spsSequence.DitheredFlats(exptime=exptime, positions=positions.round(5), dcbOn=dcbOn, dcbOff=dcbOff,
                                        **kwargs)
        self.process(cmd, seq=seq)

    def scienceObject(self, cmd):
        """sps exposure with given exptime. """
        cmdKeys = cmd.cmd.keywords
        kwargs = safeKwargs(cmd, **cmdKwargs(cmdKeys))

        if not self.sanityCheck(cmd, **kwargs):
            cmd.fail('text="sanityCheck has failed')
            return

        exptime = cmdKeys['exptime'].values

        seq = spsSequence.Object(seqtype='scienceObject', exptime=exptime, **kwargs)
        self.process(cmd, seq=seq)

    def scienceArc(self, cmd):
        """sps arc(s) with given exptime. """
        cmdKeys = cmd.cmd.keywords
        dcbOn, dcbOff = dcbKwargs(cmdKeys)
        kwargs = safeKwargs(cmd, **cmdKwargs(cmdKeys))

        if not self.sanityCheck(cmd, **kwargs):
            cmd.fail('text="sanityCheck has failed')
            return

        if dcbOn['attenuator'] is not None and self.actor.site != 'L':
            raise ValueError('You can only set attenuator at LAM')

        iisOn, iisOff = iisKwargs(cmdKeys)
        exptime = cmdKeys['exptime'].values

        seq = spsSequence.Arc(seqtype='scienceArc', exptime=exptime, dcbOn=dcbOn, dcbOff=dcbOff, iisOn=iisOn,
                              iisOff=iisOff, **kwargs)
        self.process(cmd, seq=seq)

    def scienceTrace(self, cmd):
        """sps flat(s), also known as fiberTrace, with given exptime. """
        cmdKeys = cmd.cmd.keywords
        dcbOn, dcbOff = dcbKwargs(cmdKeys)
        kwargs = safeKwargs(cmd, **cmdKwargs(cmdKeys))

        if not self.sanityCheck(cmd, **kwargs):
            cmd.fail('text="sanityCheck has failed')
            return

        if dcbOn['attenuator'] is not None and self.actor.site != 'L':
            raise ValueError('You can only set attenuator at LAM')

        dcbOn['on'] = 'halogen'
        exptime = cmdKeys['exptime'].values

        seq = spsSequence.Flat(seqtype='scienceTrace', exptime=exptime, dcbOn=dcbOn, dcbOff=dcbOff, **kwargs)
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

    def doExpose(self, cmd):
        """sps exposure with given exptime. """
        cmdKeys = cmd.cmd.keywords
        exptime = cmdKeys['exptime'].values

        seq = spsSequence.Object(exptime=exptime, **cmdKwargs(cmdKeys))
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

    def doTimedDitheredFlats(self, cmd):
        """ditheredFlat sequence, also known as masterFlat, controlled by lamp time. """
        cmdKeys = cmd.cmd.keywords
        kwargs = cmdKwargs(cmdKeys)
        timedLamps = timedDcbKwargs(cmdKeys)

        pixels = cmdKeys['pixels'].values[0] if 'pixels' in cmdKeys else 0.3
        nPositions = cmdKeys['nPositions'].values[0] if 'nPositions' in cmdKeys else 20
        nPositions = (nPositions // 2) * 2
        positions = np.linspace(-nPositions * pixels, nPositions * pixels, 2 * nPositions + 1)
        kwargs['name'] = 'calibrationData' if not kwargs['name'] else kwargs['name']

        seq = timedSpsSequence.DitheredFlats(positions=positions.round(5), timedLamps=timedLamps, **kwargs)
        self.process(cmd, seq=seq)

    def doTimedArc(self, cmd):
        """sps arc(s) controlled by lamp times """
        cmdKeys = cmd.cmd.keywords
        timedLamps = timedDcbKwargs(cmdKeys)

        seq = timedSpsSequence.Arc(timedLamps=timedLamps, **cmdKwargs(cmdKeys))
        self.process(cmd, seq=seq)

    def doTimedFlat(self, cmd):
        """sps flat(s), also known as fiberTrace, controlled by lamp time. """
        cmdKeys = cmd.cmd.keywords
        timedLamps = timedDcbKwargs(cmdKeys)

        seq = timedSpsSequence.Flat(timedLamps=timedLamps, **cmdKwargs(cmdKeys))
        self.process(cmd, seq=seq)

    def hexapodStability(self, cmd):
        """acquire hexapod stability grid. By default 12x12 and 3 duplicates at each position. """
        cmdKeys = cmd.cmd.keywords
        timedLamps = timedDcbKwargs(cmdKeys)
        kwargs = cmdKwargs(cmdKeys)
        kwargs['duplicate'] = max(kwargs['duplicate'], 3)

        position = cmdKeys['position'].values if 'position' in cmdKeys else [-0.05, 0.055, 0.01]

        seq = timedSpsSequence.HexapodStability(position=np.arange(*position), timedLamps=timedLamps, **kwargs)
        self.process(cmd, seq=seq)

    def doTimedDitheredArcs(self, cmd):
        """dithered Arc(s), controlled by lamp time.  """
        cmdKeys = cmd.cmd.keywords
        timedLamps = timedDcbKwargs(cmdKeys)

        pixels = cmdKeys['pixels'].values[0]
        doMinus = 'doMinus' in cmdKeys

        seq = timedSpsSequence.DitheredArcs(pixels=pixels, doMinus=doMinus, timedLamps=timedLamps, **cmdKwargs(cmdKeys))
        self.process(cmd, seq=seq)

    def doTimedDetThroughFocus(self, cmd):
        """sps detector motors through focus with given exptime. """
        cmdKeys = cmd.cmd.keywords
        timedLamps = timedDcbKwargs(cmdKeys)

        start, stop, num = cmdKeys['position'].values
        tilt = np.array(cmdKeys['tilt'].values) if 'tilt' in cmdKeys else np.zeros(3)
        positions = np.array([np.linspace(start, stop - np.max(tilt), num=int(num)), ] * 3).transpose() + tilt

        seq = timedSpsSequence.DetThroughFocus(positions=positions.round(2), timedLamps=timedLamps,
                                               **cmdKwargs(cmdKeys))
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
