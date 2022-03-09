from importlib import reload

import ics.iicActor.sps.engineering as engineering
import ics.iicActor.sps.sequenceList as spsSequence
import ics.iicActor.sps.timed as timedSpsSequence
import ics.iicActor.utils.lib as iicUtils
import numpy as np
import opscore.protocols.keys as keys
import opscore.protocols.types as types

reload(spsSequence)
reload(timedSpsSequence)
reload(engineering)
reload(iicUtils)


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


class DcbCmd(object):

    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor
        self.seq = None

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        seqArgs = '[<name>] [<comments>] [@doTest] [<head>] [<tail>]'
        identArgs = '[<cam>] [<arm>] [<sm>]'
        commonArgs = f'{identArgs} [<duplicate>] {seqArgs}'
        dcbArgs = f'[<switchOn>] [<switchOff>] [<warmingTime>] [force]'

        self.vocab = [
            ('ditheredFlats', f'<exptime> [<pixels>] [<nPositions>] [<warmingTime>] [force] [noLampCtl] [switchOff] {commonArgs}', self.ditheredFlats),
            ('expose', f'arc <exptime> {dcbArgs} {commonArgs}', self.doArc),
            ('expose', f'flat <exptime> [<warmingTime>] [force] [noLampCtl] [switchOff] {commonArgs}', self.doFlat),

            ('slit', f'throughfocus <exptime> <position> {dcbArgs} {commonArgs}', self.slitThroughFocus),
            ('detector', f'throughfocus <exptime> <position> [<tilt>] {dcbArgs} {commonArgs}', self.detThroughFocus),
            ('dither', f'arc <exptime> <pixels> [doMinus] {dcbArgs} {commonArgs}', self.ditheredArcs),
            ('defocus', f'arc <exptime> <position> {dcbArgs} {commonArgs}', self.defocusedArcs),
            ('custom', '[<name>] [<comments>] [<head>] [<tail>]', self.custom),

        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary('iic_dcb', (1, 1),
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
                                        keys.Key('position', types.Float() * (1, 3),
                                                 help='slit/motor position for throughfocus same args as np.linspace'),
                                        keys.Key('tilt', types.Float() * (1, 3), help='motor tilt (a, b, c)'),
                                        keys.Key('nPositions', types.Int(),
                                                 help='Number of position for dithered flats (default : 20)'),
                                        keys.Key('pixels', types.Float(), help='dithering step in pixels'),
                                        keys.Key('warmingTime', types.Float(), help='customizable warming time'),

                                        )

    @property
    def resourceManager(self):
        return self.actor.resourceManager

    def ditheredFlats(self, cmd):
        """
        `iic ditheredFlats exptime=??? [pixels=FF.F] [nPositions=N] [warmingTime=FF.F] [force] [noLampCtl] [switchOff]
        [cam=???] [arm=???] [sm=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"] [@doTest] [head=???] [tail=???]`

        Take a set of dithered fiberTrace with a given pixel step (default=0.3).
        Sequence is referenced in opdb as iic_sequence.seqtype=ditheredFlats.

        Parameters
        ---------
        exptime : `float`
            shutter exposure time.
        pixels : `float`
            dithering step in pixels.
        nPositions : `int`
            number of dithered positions on each side of home (nTotalPosition=nPositions * 2 + 1).
        warmingTime : `float`
            optional continuum lamp warming time.
        force : `bool`
            skip any lamp warmup logic.
        noLampCtl : `bool`
            ignore continuum lamp control.
        switchOff : `bool`
            switch continuum lamp at the end.
        cam : list of `str`
           List of camera to expose, default=all.
        arm : list of `str`
           List of arm to expose, default=all.
        sm : list of `int`
           List of spectrograph module to expose, default=all.
        duplicate : `int`
           Number of exposure, default=1.
        name : `str`
           To be inserted in opdb:iic_sequence.name.
        comments : `str`
           To be inserted in opdb:iic_sequence.comments.
        doTest : `bool`
           image/exposure type will be labelled as test, default=flat.
        head : list of `str`
            list of command to be launched before the sequence.
        tail : list of `str`
            list of command to be launched after the sequence.
        """
        cmdKeys = cmd.cmd.keywords

        dcbOn, dcbOff = dcbKwargs(cmdKeys, forceHalogen=True)
        exptime = cmdKeys['exptime'].values

        seqKwargs = iicUtils.genSequenceKwargs(cmd)
        seqKwargs['name'] = 'calibProduct' if not seqKwargs['name'] else seqKwargs['name']

        pixels = cmdKeys['pixels'].values[0] if 'pixels' in cmdKeys else 0.3
        nPositions = cmdKeys['nPositions'].values[0] if 'nPositions' in cmdKeys else 20
        nPositions = (nPositions // 2) * 2
        positions = np.linspace(-nPositions * pixels, nPositions * pixels, 2 * nPositions + 1).round(2)
        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1

        job = self.resourceManager.request(cmd, spsSequence.DitheredFlats)
        job.instantiate(cmd, exptime=exptime, positions=positions, dcbOn=dcbOn, dcbOff=dcbOff, duplicate=duplicate,
                        **seqKwargs)
        job.fire(cmd)

    def doArc(self, cmd):
        """
        `iic expose arc exptime=??? [switchOn=???] [switchOff=???] [warmingTime=FF.F] [force] [cam=???] [arm=???]
        [sm=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"] [@doTest] [head=???] [tail=???]`

        Take a set of arc exposure.
        Sequence is referenced in opdb as iic_sequence.seqtype=arcs.

        Parameters
        ---------
        exptime : `float`
            shutter exposure time.
        switchOn : list of str`
           list of dcb lamp to turn on before the exposure(s).
        switchOff : list of str`
           list of dcb lamp to turn off after the exposure(s).
        warmingTime : `float`
            optional lamp warming time.
        force : `bool`
            skip any lamp warmup logic.
        cam : list of `str`
           List of camera to expose, default=all
        arm : list of `str`
           List of arm to expose, default=all
        sm : list of `int`
           List of spectrograph module to expose, default=all
        duplicate : `int`
           Number of exposure, default=1
        name : `str`
           To be inserted in opdb:iic_sequence.name.
        comments : `str`
           To be inserted in opdb:iic_sequence.comments.
        doTest : `bool`
           image/exposure type will be labelled as test, default=arc
        head : list of `str`
            list of command to be launched before the sequence.
        tail : list of `str`
            list of command to be launched after the sequence.
        """
        cmdKeys = cmd.cmd.keywords

        seqKwargs = iicUtils.genSequenceKwargs(cmd, customMade=True)
        dcbOn, dcbOff = dcbKwargs(cmdKeys)
        exptime = cmdKeys['exptime'].values

        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1

        job = self.resourceManager.request(cmd, spsSequence.Arcs)
        job.instantiate(cmd, exptime=exptime, dcbOn=dcbOn, dcbOff=dcbOff, duplicate=duplicate, **seqKwargs)
        job.fire(cmd)

    def doFlat(self, cmd):
        """
        `iic expose flat exptime=??? [warmingTime=FF.F] [force] [noLampCtl] [switchOff] [cam=???] [arm=???] [sm=???]
        [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"] [@doTest] [head=???] [tail=???]`

        Take a set of flat exposure.
        Sequence is referenced in opdb as iic_sequence.seqtype=flats.

        Parameters
        ---------
        exptime : `float`
            shutter exposure time.
        warmingTime : `float`
            optional continuum lamp warming time.
        force : `bool`
            skip any lamp warmup logic.
        noLampCtl : `bool`
            ignore continuum lamp control.
        switchOff : `bool`
            switch continuum lamp at the end.
        cam : list of `str`
           List of camera to expose, default=all
        arm : list of `str`
           List of arm to expose, default=all
        sm : list of `int`
           List of spectrograph module to expose, default=all
        duplicate : `int`
           Number of exposure, default=1
        name : `str`
           To be inserted in opdb:iic_sequence.name.
        comments : `str`
           To be inserted in opdb:iic_sequence.comments.
        doTest : `bool`
           image/exposure type will be labelled as test, default=flat
        head : list of `str`
            list of command to be launched before the sequence.
        tail : list of `str`
            list of command to be launched after the sequence.
        """
        cmdKeys = cmd.cmd.keywords

        seqKwargs = iicUtils.genSequenceKwargs(cmd, customMade=True)
        dcbOn, dcbOff = dcbKwargs(cmdKeys, forceHalogen=True)
        exptime = cmdKeys['exptime'].values
        window = cmdKeys['window'].values if 'window' in cmdKeys else False

        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1

        job = self.resourceManager.request(cmd, spsSequence.Flats)
        job.instantiate(cmd, exptime=exptime, dcbOn=dcbOn, dcbOff=dcbOff, duplicate=duplicate, window=window,
                        **seqKwargs)
        job.fire(cmd)

    def slitThroughFocus(self, cmd):
        """
        `iic slit throughfocus exptime=??? position=??? [switchOn=???] [switchOff=???] [warmingTime=FF.F] [force]
        [cam=???] [arm=???] [sm=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"] [@doTest] [head=???] [tail=???]`

        Take Arc dataset through focus using FCA hexapod.
        Sequence is referenced in opdb as iic_sequence.seqtype=slitThroughFocus.

        Parameters
        ---------
        exptime : `float`
            shutter exposure time.
        position: `float`, `float`, `int`
            fca position constructor, same logic as np.linspace(start, stop, num).
        switchOn : list of str`
           list of dcb lamp to turn on before the exposure(s).
        switchOff : list of str`
           list of dcb lamp to turn off after the exposure(s).
        warmingTime : `float`
            optional lamp warming time.
        force : `bool`
            skip any lamp warmup logic.
        cam : list of `str`
           List of camera to expose, default=all
        arm : list of `str`
           List of arm to expose, default=all
        sm : list of `int`
           List of spectrograph module to expose, default=all
        duplicate : `int`
           Number of exposure, default=1
        name : `str`
           To be inserted in opdb:iic_sequence.name.
        comments : `str`
           To be inserted in opdb:iic_sequence.comments.
        head : list of `str`
            list of command to be launched before the sequence.
        tail : list of `str`
            list of command to be launched after the sequence.
        doTest : `bool`
           image/exposure type will be labelled as test, default=arc.
        """

        cmdKeys = cmd.cmd.keywords
        seqKwargs = iicUtils.genSequenceKwargs(cmd, customMade=True)

        dcbOn, dcbOff = dcbKwargs(cmdKeys)
        exptime = cmdKeys['exptime'].values

        start, stop, num = cmdKeys['position'].values
        positions = np.linspace(start, stop, num=int(num)).round(6)
        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1

        job = self.resourceManager.request(cmd, spsSequence.SlitThroughFocus)
        job.instantiate(cmd, exptime=exptime, positions=positions, dcbOn=dcbOn, dcbOff=dcbOff, duplicate=duplicate,
                        **seqKwargs)
        job.fire(cmd)

    def detThroughFocus(self, cmd):
        """
        `iic detector throughfocus exptime=??? position=??? [tilt=???] [switchOn=???] [switchOff=???]
        [warmingTime=FF.F] [force] [cam=???] [arm=???] [sm=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"]
        [@doTest] [head=???] [tail=???]`

        Take Arc dataset through focus using Focal Plane Array focus motors.
        Sequence is referenced in opdb as iic_sequence.seqtype=detThroughFocus.

        Parameters
        ---------
        exptime : `float`
            shutter exposure time.
        position: `float`, `float`, `int`
            fpa position constructor, same logic as np.linspace(start, stop, num).
        tilt: `float`, `float`, `float`
            fpa A,B,C motor tilt position.
        switchOn : list of str`
           list of dcb lamp to turn on before the exposure(s).
        switchOff : list of str`
           list of dcb lamp to turn off after the exposure(s).
        warmingTime : `float`
            optional lamp warming time.
        force : `bool`
            skip any lamp warmup logic.
        cam : list of `str`
           List of camera to expose, default=all
        arm : list of `str`
           List of arm to expose, default=all
        sm : list of `int`
           List of spectrograph module to expose, default=all
        duplicate : `int`
           Number of exposure, default=1
        name : `str`
           To be inserted in opdb:iic_sequence.name.
        comments : `str`
           To be inserted in opdb:iic_sequence.comments.
        head : list of `str`
            list of command to be launched before the sequence.
        tail : list of `str`
            list of command to be launched after the sequence.
        doTest : `bool`
           image/exposure type will be labelled as test, default=arc.
        """
        cmdKeys = cmd.cmd.keywords
        seqKwargs = iicUtils.genSequenceKwargs(cmd, customMade=True)

        dcbOn, dcbOff = dcbKwargs(cmdKeys)
        exptime = cmdKeys['exptime'].values

        start, stop, num = cmdKeys['position'].values
        tilt = np.array(cmdKeys['tilt'].values) if 'tilt' in cmdKeys else np.zeros(3)
        positions = np.array([np.linspace(start, stop - np.max(tilt), num=int(num)), ] * 3).transpose() + tilt
        positions = positions.round(2)
        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1

        job = self.resourceManager.request(cmd, spsSequence.DetThroughFocus)
        job.instantiate(cmd, exptime=exptime, positions=positions, dcbOn=dcbOn, dcbOff=dcbOff, duplicate=duplicate,
                        **seqKwargs)
        job.fire(cmd)

    def ditheredArcs(self, cmd):
        """
        `iic dither arc exptime=??? pixels=FF.F [doMinus] [switchOn=???] [switchOff=???] [warmingTime=FF.F] [force]
        [cam=???] [arm=???] [sm=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"] [@doTest] [head=???] [tail=???]`

        Take a set of dithered Arc with a given pixel step.
        default step is set to 0.5 pixels -> 4 positions(dither_x, dither_y) = [(0,0), (0.5,0), (0, 0.5), (0.5, 0.5)].
        Sequence is referenced in opdb as iic_sequence.seqtype=ditheredArcs.

        Parameters
        ---------
        exptime : `float`
            shutter exposure time.
        pixels : `float`
            dithering step in pixels.
        doMinus : `bool`
           if True, add negative dither step in the position grid.
        switchOn : list of str`
           list of dcb lamp to turn on before the exposure(s).
        switchOff : list of str`
           list of dcb lamp to turn off after the exposure(s).
        warmingTime : `float`
            optional lamp warming time.
        force : `bool`
            skip any lamp warmup logic.
        cam : list of `str`
           List of camera to expose, default=all
        arm : list of `str`
           List of arm to expose, default=all
        sm : list of `int`
           List of spectrograph module to expose, default=all
        duplicate : `int`
           Number of exposure, default=1
        name : `str`
           To be inserted in opdb:iic_sequence.name.
        comments : `str`
           To be inserted in opdb:iic_sequence.comments.
        doTest : `bool`
           image/exposure type will be labelled as test, default=arc.
        head : list of `str`
            list of command to be launched before the sequence.
        tail : list of `str`
            list of command to be launched after the sequence.
        """
        cmdKeys = cmd.cmd.keywords
        seqKwargs = iicUtils.genSequenceKwargs(cmd, customMade=True)

        dcbOn, dcbOff = dcbKwargs(cmdKeys)
        exptime = cmdKeys['exptime'].values

        pixels = cmdKeys['pixels'].values[0]
        doMinus = 'doMinus' in cmdKeys
        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1

        job = self.resourceManager.request(cmd, spsSequence.DitheredArcs)
        job.instantiate(cmd, exptime=exptime, pixels=pixels, doMinus=doMinus, dcbOn=dcbOn, dcbOff=dcbOff,
                        duplicate=duplicate, **seqKwargs)
        job.fire(cmd)

    def defocusedArcs(self, cmd):
        """
        `iic defocus arc exptime=??? position=??? [switchOn=???] [switchOff=???] [warmingTime=FF.F] [force] [cam=???]
        [arm=???] [sm=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"] [@doTest] [head=???] [tail=???]`

        Take Arc dataset through focus using fca hexapod, exposure time is scaled such as psf max flux ~= constant
        Sequence is referenced in opdb as iic_sequence.seqtype=defocusedArcs.

        Parameters
        ---------
        exptime : `float`
            shutter exposure time.
        position: `float`, `float`, `int`
            fca hexapod position constructor, same logic as np.linspace(start, stop, num).
        switchOn : list of str`
           list of dcb lamp to turn on before the exposure(s).
        switchOff : list of str`
           list of dcb lamp to turn off after the exposure(s).
        warmingTime : `float`
            optional lamp warming time.
        force : `bool`
            skip any lamp warmup logic.
        cam : list of `str`
           List of camera to expose, default=all
        arm : list of `str`
           List of arm to expose, default=all
        sm : list of `int`
           List of spectrograph module to expose, default=all
        duplicate : `int`
           Number of exposure, default=1
        name : `str`
           To be inserted in opdb:iic_sequence.name.
        comments : `str`
           To be inserted in opdb:iic_sequence.comments.
        doTest : `bool`
           image/exposure type will be labelled as test, default=arc.
        head : list of `str`
            list of command to be launched before the sequence.
        tail : list of `str`
            list of command to be launched after the sequence.
        """
        cmdKeys = cmd.cmd.keywords
        seqKwargs = iicUtils.genSequenceKwargs(cmd, customMade=True)
        dcbOn, dcbOff = dcbKwargs(cmdKeys)
        exptime = cmdKeys['exptime'].values

        start, stop, num = cmdKeys['position'].values
        positions = np.linspace(start, stop, num=int(num)).round(6)
        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1

        job = self.resourceManager.request(cmd, spsSequence.DefocusedArcs)
        job.instantiate(cmd, exp_time_0=exptime, positions=positions, dcbOn=dcbOn, dcbOff=dcbOff, duplicate=duplicate,
                        **seqKwargs)
        job.fire(cmd)

    def custom(self, cmd):
        """
        `iic custom [name=\"SSS\"] [comments=\"SSS\"] [head=???] [tail=???]`

        Customized sequence of commands.

        Parameters
        ---------
        name : `str`
           To be inserted in opdb:iic_sequence.name.
        comments : `str`
           To be inserted in opdb:iic_sequence.comments.
        head : list of `str`
            list of command to be describe the sequence.
        tail : list of `str`
            list of command to be launched after the sequence.
        """
        seqKwargs = iicUtils.genSequenceKwargs(cmd, customMade=True)

        job = self.resourceManager.request(cmd, spsSequence.Custom)
        job.instantiate(cmd, **seqKwargs)
        job.fire(cmd)
