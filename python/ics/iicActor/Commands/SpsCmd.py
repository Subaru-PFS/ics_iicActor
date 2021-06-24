from importlib import reload

import ics.iicActor.sps.sequenceList as spsSequence
import ics.iicActor.sps.timed as timedSpsSequence
import numpy as np
import opscore.protocols.keys as keys
import opscore.protocols.types as types

reload(spsSequence)
reload(timedSpsSequence)


def genSeqKwargs(cmd, customMade=True):
    cmdKeys = cmd.cmd.keywords
    head = cmdKeys['head'].values if 'head' in cmdKeys else None
    tail = cmdKeys['tail'].values if 'tail' in cmdKeys else None

    if not customMade and (head is not None or tail is not None):
        cmd.warn('text="not parsing head or tail here, sorry...')
        head = None
        tail = None

    name = cmdKeys['name'].values[0] if 'name' in cmdKeys else ''
    comments = cmdKeys['comments'].values[0] if 'comments' in cmdKeys else ''
    doTest = 'doTest' in cmdKeys

    return dict(name=name, comments=comments, head=head, tail=tail, doTest=doTest)


def dcbKwargs(cmdKeys, forceHalogen=False):
    switchOn = ','.join(cmdKeys['switchOn'].values) if 'switchOn' in cmdKeys else None
    switchOn = 'halogen' if forceHalogen and 'noLampCtl' not in cmdKeys else switchOn
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


def fetchExpTime(cmdKeys):
    try:
        exptime = cmdKeys['exptime'].values
        seqLib = spsSequence
    except KeyError:
        exptime = timedDcbKwargs(cmdKeys)
        seqLib = timedSpsSequence

    return exptime, seqLib


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
        seqArgs = '[<name>] [<comments>] [<head>] [<tail>] [@doTest]'
        identArgs = '[<cam>] [<arm>] [<sm>]'
        commonArgs = f'{identArgs} [<duplicate>] {seqArgs}'
        dcbArgs = f'[<switchOn>] [<switchOff>] [<warmingTime>] [<attenuator>] [force]'

        timedDcbArcArgs = '[<hgar>] [<argon>] [<neon>] [<krypton>]'
        self.vocab = [
            ('masterBiases', f'{commonArgs}', self.masterBiases),
            ('masterDarks', f'[<exptime>] {commonArgs}', self.masterDarks),
            ('ditheredFlats', f'<exptime> [<pixels>] [<nPositions>] [switchOff] {dcbArgs} {commonArgs}',
             self.ditheredFlats),
            ('scienceArc', f'<exptime> {dcbArgs} {commonArgs}', self.scienceArc),
            ('scienceTrace', f'<exptime> [switchOff] {dcbArgs} {commonArgs}', self.scienceTrace),
            ('scienceObject', f'<exptime> {commonArgs}', self.scienceObject),
            ('bias', f'{commonArgs}', self.doBias),
            ('dark', f'<exptime> {commonArgs}', self.doDark),
            ('expose', f'arc <exptime> {dcbArgs} {commonArgs}', self.scienceArc),
            ('expose', f'flat <exptime> [noLampCtl] [switchOff] {dcbArgs} {commonArgs}', self.scienceTrace),

            ('slit', f'throughfocus <exptime> <position> {dcbArgs} {commonArgs}', self.slitThroughFocus),
            ('detector', f'throughfocus <exptime> <position> [<tilt>] {dcbArgs} {commonArgs}', self.detThroughFocus),
            ('dither', f'arc <exptime> <pixels> [doMinus] {dcbArgs} {commonArgs}', self.ditheredArcs),
            ('defocus', f'arc <exptime> <position> {dcbArgs} {commonArgs}', self.defocusedArcs),
            ('custom', '[<name>] [<comments>] [<head>] [<tail>]', self.custom),

            ('ditheredFlats', f'<halogen> [<pixels>] [<nPositions>] {commonArgs}', self.ditheredFlats),
            ('scienceArc', f'{timedDcbArcArgs} {commonArgs}', self.scienceArc),
            ('scienceTrace', f'<halogen> {commonArgs}', self.scienceTrace),
            ('expose', f'arc {timedDcbArcArgs} {commonArgs}', self.scienceArc),
            ('expose', f'flat <halogen> {commonArgs}', self.scienceTrace),
            ('test', f'hexapodStability {timedDcbArcArgs} [<position>] {commonArgs}', self.hexapodStability),
            ('dither', f'arc {timedDcbArcArgs} <pixels> [doMinus] {commonArgs}', self.ditheredArcs),
            ('detector', f'throughfocus {timedDcbArcArgs} <position> [<tilt>] {commonArgs}',
             self.detThroughFocus),
            ('defocus', f'arc {timedDcbArcArgs} <position> {commonArgs}', self.defocusedArcs),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary('iic_iic', (1, 1),
                                        keys.Key('exptime', types.Float() * (1,), help='exptime list (seconds)'),
                                        keys.Key('duplicate', types.Int(), help='exposure duplicate (1 is default)'),
                                        keys.Key('cam', types.String() * (1,), help='camera(s) to take exposure from'),
                                        keys.Key('arm', types.String() * (1,), help='arm to take exposure from'),
                                        keys.Key('sm', types.Int() * (1,),
                                                 help='spectrograph module(s) to take exposure from'),
                                        keys.Key('name', types.String(), help='iic_sequence name'),
                                        keys.Key('comments', types.String(), help='iic_sequence comments'),
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

    @property
    def resourceManager(self):
        return self.actor.resourceManager

    def masterBiases(self, cmd):
        """sps master bias(es). """
        cmdKeys = cmd.cmd.keywords

        seqKwargs = genSeqKwargs(cmd, customMade=False)
        seqKwargs['name'] = 'calibProduct' if not seqKwargs['name'] else seqKwargs['name']
        duplicate = min(cmdKeys['duplicate'].values[0], 15) if 'duplicate' in cmdKeys else 15

        job = self.resourceManager.request(cmd, spsSequence.MasterBiases)
        job.instantiate(cmd, duplicate=duplicate, **seqKwargs)

        job.fire(cmd)

    def masterDarks(self, cmd):
        """sps master dark(s). """
        cmdKeys = cmd.cmd.keywords

        seqKwargs = genSeqKwargs(cmd, customMade=False)
        seqKwargs['name'] = 'calibProduct' if not seqKwargs['name'] else seqKwargs['name']
        duplicate = min(cmdKeys['duplicate'].values[0], 15) if 'duplicate' in cmdKeys else 15
        exptime = cmdKeys['exptime'].values if 'exptime' in cmdKeys else [300]

        job = self.resourceManager.request(cmd, spsSequence.MasterDarks)

        job.instantiate(cmd, exptime=exptime, duplicate=duplicate, **seqKwargs)
        job.fire(cmd)

    def ditheredFlats(self, cmd):
        """dithered flat(fiberTrace) with given exptime. Used to construct masterFlat """
        cmdKeys = cmd.cmd.keywords

        dcbOn, dcbOff = dcbKwargs(cmdKeys, forceHalogen=True)
        exptime, seqLib = fetchExpTime(cmdKeys)

        seqKwargs = genSeqKwargs(cmd, customMade=False)
        seqKwargs['name'] = 'calibProduct' if not seqKwargs['name'] else seqKwargs['name']

        pixels = cmdKeys['pixels'].values[0] if 'pixels' in cmdKeys else 0.3
        nPositions = cmdKeys['nPositions'].values[0] if 'nPositions' in cmdKeys else 20
        nPositions = (nPositions // 2) * 2
        positions = np.linspace(-nPositions * pixels, nPositions * pixels, 2 * nPositions + 1).round(2)
        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1

        job = self.resourceManager.request(cmd, seqLib.DitheredFlats)
        job.instantiate(cmd, exptime=exptime, positions=positions, dcbOn=dcbOn, dcbOff=dcbOff, duplicate=duplicate,
                        **seqKwargs)
        job.fire(cmd)

    def scienceArc(self, cmd):
        """sps science arcs. """
        cmdKeys = cmd.cmd.keywords
        isScience = 'arc' not in cmdKeys

        seqKwargs = genSeqKwargs(cmd, customMade=not isScience)
        dcbOn, dcbOff = dcbKwargs(cmdKeys)
        exptime, seqLib = fetchExpTime(cmdKeys)

        seqObj = seqLib.ScienceArc if isScience else seqLib.Arcs
        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1

        job = self.resourceManager.request(cmd, seqObj)
        job.instantiate(cmd, exptime=exptime, dcbOn=dcbOn, dcbOff=dcbOff, duplicate=duplicate, **seqKwargs)
        job.fire(cmd)

    def scienceTrace(self, cmd):
        """sps bias(es). """
        cmdKeys = cmd.cmd.keywords
        isScience = 'flat' not in cmdKeys

        seqKwargs = genSeqKwargs(cmd, customMade=not isScience)
        forceHalogen = 'halogen' not in cmdKeys
        dcbOn, dcbOff = dcbKwargs(cmdKeys, forceHalogen=forceHalogen)
        exptime, seqLib = fetchExpTime(cmdKeys)

        seqObj = seqLib.ScienceTrace if isScience else seqLib.Flats
        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1

        job = self.resourceManager.request(cmd, seqObj)
        job.instantiate(cmd, exptime=exptime, dcbOn=dcbOn, dcbOff=dcbOff, duplicate=duplicate, **seqKwargs)
        job.fire(cmd)

    def scienceObject(self, cmd):
        """sps bias(es). """
        cmdKeys = cmd.cmd.keywords
        seqKwargs = genSeqKwargs(cmd, customMade=False)

        exptime = cmdKeys['exptime'].values
        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1

        job = self.resourceManager.request(cmd, spsSequence.Object)
        job.instantiate(cmd, exptime=exptime, duplicate=duplicate, **seqKwargs)

        job.fire(cmd)

    def doBias(self, cmd):
        """sps bias(es). """
        cmdKeys = cmd.cmd.keywords
        seqKwargs = genSeqKwargs(cmd)

        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1

        job = self.resourceManager.request(cmd, spsSequence.Biases)
        job.instantiate(cmd, duplicate=duplicate, **seqKwargs)

        job.fire(cmd)

    def doDark(self, cmd):
        """sps dark(s) with given exptime. """
        cmdKeys = cmd.cmd.keywords
        seqKwargs = genSeqKwargs(cmd, customMade=False)

        exptime = cmdKeys['exptime'].values
        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1

        job = self.resourceManager.request(cmd, spsSequence.Darks)
        job.instantiate(cmd, exptime=exptime, duplicate=duplicate, **seqKwargs)

        job.fire(cmd)

    def slitThroughFocus(self, cmd):
        """sps slit through focus with given exptime. """
        cmdKeys = cmd.cmd.keywords
        seqKwargs = genSeqKwargs(cmd)

        dcbOn, dcbOff = dcbKwargs(cmdKeys)
        exptime, seqLib = fetchExpTime(cmdKeys)

        start, stop, num = cmdKeys['position'].values
        positions = np.linspace(start, stop, num=int(num)).round(6)
        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1

        job = self.resourceManager.request(cmd, seqLib.SlitThroughFocus)
        job.instantiate(cmd, exptime=exptime, positions=positions, dcbOn=dcbOn, dcbOff=dcbOff, duplicate=duplicate,
                        **seqKwargs)
        job.fire(cmd)

    def detThroughFocus(self, cmd):
        """sps detector motors through focus with given exptime. """
        cmdKeys = cmd.cmd.keywords
        seqKwargs = genSeqKwargs(cmd)

        dcbOn, dcbOff = dcbKwargs(cmdKeys)
        exptime, seqLib = fetchExpTime(cmdKeys)

        start, stop, num = cmdKeys['position'].values
        tilt = np.array(cmdKeys['tilt'].values) if 'tilt' in cmdKeys else np.zeros(3)
        positions = np.array([np.linspace(start, stop - np.max(tilt), num=int(num)), ] * 3).transpose() + tilt
        positions = positions.round(2)
        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1

        job = self.resourceManager.request(cmd, seqLib.DetThroughFocus)
        job.instantiate(cmd, exptime=exptime, positions=positions, dcbOn=dcbOn, dcbOff=dcbOff, duplicate=duplicate,
                        **seqKwargs)
        job.fire(cmd)

    def ditheredArcs(self, cmd):
        """dithered Arc(s) with given exptime. """
        cmdKeys = cmd.cmd.keywords
        seqKwargs = genSeqKwargs(cmd)

        dcbOn, dcbOff = dcbKwargs(cmdKeys)
        exptime, seqLib = fetchExpTime(cmdKeys)

        pixels = cmdKeys['pixels'].values[0]
        doMinus = 'doMinus' in cmdKeys
        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1

        job = self.resourceManager.request(cmd, seqLib.DitheredArcs)
        job.instantiate(cmd, exptime=exptime, pixels=pixels, doMinus=doMinus, dcbOn=dcbOn, dcbOff=dcbOff,
                        duplicate=duplicate, **seqKwargs)
        job.fire(cmd)

    def defocusedArcs(self, cmd):
        """defocused Arc(s) with given exptime. """
        cmdKeys = cmd.cmd.keywords
        seqKwargs = genSeqKwargs(cmd)
        dcbOn, dcbOff = dcbKwargs(cmdKeys)
        exptime, seqLib = fetchExpTime(cmdKeys)

        start, stop, num = cmdKeys['position'].values
        positions = np.linspace(start, stop, num=int(num)).round(6)
        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1

        job = self.resourceManager.request(cmd, seqLib.DefocusedArcs)
        job.instantiate(cmd, exp_time_0=exptime, positions=positions, dcbOn=dcbOn, dcbOff=dcbOff, duplicate=duplicate,
                        **seqKwargs)
        job.fire(cmd)

    def hexapodStability(self, cmd):
        """acquire hexapod stability grid. By default 12x12 and 3 duplicates at each position. """
        cmdKeys = cmd.cmd.keywords
        seqKwargs = genSeqKwargs(cmd)
        timedLamps = timedDcbKwargs(cmdKeys)

        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 3
        position = cmdKeys['position'].values if 'position' in cmdKeys else [-0.05, 0.055, 0.01]
        position = np.arange(*position)

        job = self.resourceManager.request(cmd, timedSpsSequence.HexapodStability)
        job.instantiate(cmd, position=position, timedLamps=timedLamps, duplicate=duplicate, **seqKwargs)
        job.fire(cmd)

    def custom(self, cmd):
        """dithered Arc(s) with given exptime. """
        seqKwargs = genSeqKwargs(cmd)

        job = self.resourceManager.request(cmd, spsSequence.Custom)
        job.instantiate(cmd, **seqKwargs)
        job.fire(cmd)
