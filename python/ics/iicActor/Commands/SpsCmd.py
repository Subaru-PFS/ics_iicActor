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


def timedLampsKwargs(cmdKeys):
    lampNames = 'halogen', 'hgcd', 'hgar', 'argon', 'neon', 'krypton', 'xenon'
    doShutterTiming = 'doShutterTiming' in cmdKeys
    timingOverHead = 5 if doShutterTiming else 0

    lampsPrepare = {name: int(round(cmdKeys[name].values[0]) + timingOverHead) for name in lampNames if name in cmdKeys}

    if not lampsPrepare:
        raise ValueError('exptime nor per-lamp time has been specified')

    lampsPrepare['shutterTiming'] = max(lampsPrepare.values()) - timingOverHead if doShutterTiming else 0

    return lampsPrepare


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
        seqArgs = '[<name>] [<comments>] [@doTest]'
        identArgs = '[<cam>] [<arm>] [<sm>]'
        commonArgs = f'{identArgs} [<duplicate>] {seqArgs}'
        timedLampsArgs = '[<hgar>] [<hgcd>] [<argon>] [<neon>] [<krypton>] [<xenon>] [@doShutterTiming]'

        self.vocab = [
            ('masterBiases', f'{commonArgs}', self.masterBiases),
            ('masterDarks', f'[<exptime>] {commonArgs}', self.masterDarks),
            ('ditheredFlats', f'<halogen> [@doShutterTiming] [<pixels>] [<nPositions>] {commonArgs}',
             self.ditheredFlats),
            ('scienceArc', f'{timedLampsArgs} {commonArgs}', self.scienceArc),
            ('scienceTrace', f'<halogen> [@doShutterTiming]  [<window>] {commonArgs}', self.scienceTrace),
            ('scienceObject', f'<exptime> [<window>] {commonArgs}', self.scienceObject),
            ('domeFlat', f'<exptime> [<window>] {commonArgs}', self.domeFlat),
            ('domeArc', f'<exptime> {commonArgs}', self.domeArc),
            ('sps', f'@startExposures <exptime> {identArgs} [<name>] [<comments>] [@doBias] [@doTest]',
             self.startExposures),

            ('bias', f'{commonArgs} [<head>] [<tail>]', self.doBias),
            ('dark', f'<exptime> {commonArgs} [<head>] [<tail>]', self.doDark),
            ('expose', f'arc {timedLampsArgs} {commonArgs} [<head>] [<tail>]', self.doArc),
            ('expose', f'flat <halogen> [<window>] {commonArgs} [<head>] [<tail>]', self.doFlat),

            ('dither', f'arc {timedLampsArgs} <pixels> [doMinus] {commonArgs} [<head>] [<tail>]', self.ditheredArcs),
            ('defocus', f'arc {timedLampsArgs} <position> {commonArgs} [<head>] [<tail>]', self.defocusedArcs),
            ('test', f'hexapodStability {timedLampsArgs} [<position>] {commonArgs}', self.hexapodStability),

            ('sps', 'rdaMove (low|med) [<sm>]', self.rdaMove),
            ('setGratingToDesign', '', self.setGratingToDesign),

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
                                        keys.Key('position', types.Float() * (1, 3),
                                                 help='slit/motor position for throughfocus same args as np.linspace'),
                                        keys.Key('nPositions', types.Int(),
                                                 help='Number of position for dithered flats (default : 20)'),
                                        keys.Key('pixels', types.Float(), help='dithering step in pixels'),
                                        keys.Key('halogen', types.Float(), help='quartz halogen lamp on time'),
                                        keys.Key('argon', types.Float(), help='Ar lamp on time'),
                                        keys.Key('hgar', types.Float(), help='HgAr lamp on time'),
                                        keys.Key('neon', types.Float(), help='Ne lamp on time'),
                                        keys.Key('krypton', types.Float(), help='Kr lamp on time'),
                                        keys.Key('hgcd', types.Float(), help='HgCd lamp on time'),
                                        keys.Key('xenon', types.Float(), help='Xenon lamp on time'),
                                        keys.Key("window", types.Int() * (1, 2),
                                                 help='first row, total number of rows to read'),

                                        )

    @property
    def resourceManager(self):
        return self.actor.resourceManager

    def masterBiases(self, cmd):
        """
        `iic masterBiases [cam=???] [arm=???] [sm=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"] [@doTest]`

        Take a set of biases.
        Sequence is referenced in opdb as iic_sequence.seqtype=masterBiases.

        Parameters
        ---------

        cam : list of `str`
           List of camera to expose, default=all
        arm : list of `str`
           List of arm to expose, default=all
        sm : list of `int`
           List of spectrograph module to expose, default=all
        duplicate : `int`
           Number of biases, default=15
        name : `str`
           To be inserted in opdb:iic_sequence.name.
        comments : `str`
           To be inserted in opdb:iic_sequence.comments.
        doTest : `bool`
           image/exposure type will be labelled as test, default=bias.
        """
        cmdKeys = cmd.cmd.keywords

        seqKwargs = iicUtils.genSequenceKwargs(cmd)
        seqKwargs['name'] = 'calibProduct' if not seqKwargs['name'] else seqKwargs['name']
        duplicate = min(cmdKeys['duplicate'].values[0], 15) if 'duplicate' in cmdKeys else 15

        job = self.resourceManager.request(cmd, spsSequence.MasterBiases)
        job.instantiate(cmd, duplicate=duplicate, **seqKwargs)

        job.fire(cmd)

    def masterDarks(self, cmd):
        """
        `iic masterDarks [exptime=???] [cam=???] [arm=???] [sm=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"] [@doTest]`

        Take a set of darks with given exptime.
        Sequence is referenced in opdb as iic_sequence.seqtype=masterDarks.

        Parameters
        ---------
        exptime : `float`
            dark exposure time.
        cam : list of `str`
           List of camera to expose, default=all
        arm : list of `str`
           List of arm to expose, default=all
        sm : list of `int`
           List of spectrograph module to expose, default=all
        duplicate : `int`
           Number of darks, default=15
        name : `str`
           To be inserted in opdb:iic_sequence.name.
        comments : `str`
           To be inserted in opdb:iic_sequence.comments.
        doTest : `bool`
           image/exposure type will be labelled as test, default=dark.
        """
        cmdKeys = cmd.cmd.keywords

        seqKwargs = iicUtils.genSequenceKwargs(cmd)
        seqKwargs['name'] = 'calibProduct' if not seqKwargs['name'] else seqKwargs['name']
        duplicate = min(cmdKeys['duplicate'].values[0], 15) if 'duplicate' in cmdKeys else 15
        exptime = cmdKeys['exptime'].values if 'exptime' in cmdKeys else [300]

        job = self.resourceManager.request(cmd, spsSequence.MasterDarks)

        job.instantiate(cmd, exptime=exptime, duplicate=duplicate, **seqKwargs)
        job.fire(cmd)

    def ditheredFlats(self, cmd):
        """
        `iic ditheredFlats halogen=FF.F [@doShutterTiming] [pixels=FF.F] [nPositions=N] [cam=???] [arm=???] [sm=???]
        [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"] [@doTest]`

        Take a set of dithered fiberTrace with a given pixel step (default=0.3).
        Sequence is referenced in opdb as iic_sequence.seqtype=ditheredFlats.

        Parameters
        ---------
        halogen : `float`
            number of second to trigger continuum lamp.
        doShutterTiming : `bool`
           if True, use the shutters to control exposure time, ie fire the lamps before opening the shutters.
        pixels : `float`
            dithering step in pixels.
        nPositions : `int`
            number of dithered positions on each side of home (nTotalPosition=nPositions * 2 + 1).
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
        """
        cmdKeys = cmd.cmd.keywords

        seqKwargs = iicUtils.genSequenceKwargs(cmd)
        seqKwargs['name'] = 'calibProduct' if not seqKwargs['name'] else seqKwargs['name']
        exptime = timedLampsKwargs(cmdKeys)

        pixels = cmdKeys['pixels'].values[0] if 'pixels' in cmdKeys else 0.3
        nPositions = cmdKeys['nPositions'].values[0] if 'nPositions' in cmdKeys else 20
        nPositions = (nPositions // 2) * 2
        positions = np.linspace(-nPositions * pixels, nPositions * pixels, 2 * nPositions + 1).round(2)
        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1

        job = self.resourceManager.request(cmd, timedSpsSequence.DitheredFlats)
        job.instantiate(cmd, exptime=exptime, positions=positions, dcbOn=dict(), dcbOff=dict(), duplicate=duplicate,
                        **seqKwargs)
        job.fire(cmd)

    def scienceArc(self, cmd):
        """
        `iic scienceArc [hgar=FF.F] [hgcd=FF.F] [argon=FF.F] [neon=FF.F] [krypton=FF.F] [xenon=FF.F] [@doShutterTiming]
        [cam=???] [arm=???] [sm=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"] [@doTest]`

        Check focus and take a set of arc exposure.
        Sequence is referenced in opdb as iic_sequence.seqtype=scienceArc.

        Parameters
        ---------
        hgar : `float`
            number of second to trigger mercury-argon lamp.
        hgcd : `float`
            number of second to trigger mercury-cadmium lamp.
        argon : `float`
            number of second to trigger argon lamp.
        neon : `float`
            number of second to trigger neon lamp.
        krypton : `float`
            number of second to trigger krypton lamp.
        xenon : `float`
            number of second to trigger xenon lamp.
        doShutterTiming : `bool`
           if True, use the shutters to control exposure time, ie fire the lamps before opening the shutters.
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
        """
        cmdKeys = cmd.cmd.keywords

        seqKwargs = iicUtils.genSequenceKwargs(cmd, customMade=False)
        exptime = timedLampsKwargs(cmdKeys)
        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1

        job = self.resourceManager.request(cmd, timedSpsSequence.ScienceArc)
        job.instantiate(cmd, exptime=exptime, dcbOn=dict(), dcbOff=dict(), duplicate=duplicate, **seqKwargs)
        job.fire(cmd)

    def scienceTrace(self, cmd):
        """
        `iic scienceTrace halogen=FF.F [@doShutterTiming] [window=???] [cam=???] [arm=???] [sm=???] [duplicate=N]
        [name=\"SSS\"] [comments=\"SSS\"] [@doTest]`

        Check focus and take a set of fiberTrace.
        Sequence is referenced in opdb as iic_sequence.seqtype=scienceTrace.
        Note that if the exposure is windowed, the seqtype will actually be scienceTrace_windowed.

        Parameters
        ---------
        halogen : `float`
            number of second to trigger continuum lamp.
        doShutterTiming : `bool`
           if True, use the shutters to control exposure time, ie fire the lamps before opening the shutters.
        window : `int`,`int`
            first row, total number of rows.
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
           image/exposure type will be labelled as test, default=flat.
        """
        cmdKeys = cmd.cmd.keywords

        seqKwargs = iicUtils.genSequenceKwargs(cmd, customMade=False)
        exptime = timedLampsKwargs(cmdKeys)
        window = cmdKeys['window'].values if 'window' in cmdKeys else False
        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1

        job = self.resourceManager.request(cmd, timedSpsSequence.ScienceTrace)
        job.instantiate(cmd, exptime=exptime, dcbOn=dict(), dcbOff=dict(), duplicate=duplicate, window=window,
                        **seqKwargs)
        job.fire(cmd)

    def scienceObject(self, cmd):
        """
        `iic scienceObject exptime=??? [window=???] [cam=???] [arm=???] [sm=???] [duplicate=N] [name=\"SSS\"]
        [comments=\"SSS\"] [@doTest]`

        Check focus and take a set of object exposure.
        Sequence is referenced in opdb as iic_sequence.seqtype=scienceObject.
        Note that if the exposure is windowed, the seqtype will actually be scienceObject_windowed.

        Parameters
        ---------
        exptime : `float`
            exposure time.
        window : `int`,`int`
            first row, total number of rows.
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
           image/exposure type will be labelled as test, default=object.
        """
        cmdKeys = cmd.cmd.keywords

        seqKwargs = iicUtils.genSequenceKwargs(cmd)
        exptime = cmdKeys['exptime'].values
        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1
        window = cmdKeys['window'].values if 'window' in cmdKeys else False

        job = self.resourceManager.request(cmd, spsSequence.Object)
        job.instantiate(cmd, exptime=exptime, duplicate=duplicate, window=window, **seqKwargs)

        job.fire(cmd)

    def domeFlat(self, cmd):
        """
        `iic domeFlat exptime=??? [window=???] [cam=???] [arm=???] [sm=???] [duplicate=N] [name=\"SSS\"]
        [comments=\"SSS\"] [@doTest]"`

        Check focus and take a set of fiberTrace, this sequence rely on an external illuminator (HSC lamps).
        Sequence is referenced in opdb as iic_sequence.seqtype=domeFlat.
        Note that if the exposure is windowed, the seqtype will actually be domeFlat_windowed.

        Parameters
        ---------
        exptime : `float`
            exposure time.
        window : `int`,`int`
            first row, total number of rows.
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
           image/exposure type will be labelled as test, default=domeflat.
        """
        cmdKeys = cmd.cmd.keywords

        seqKwargs = iicUtils.genSequenceKwargs(cmd, customMade=False)
        exptime = cmdKeys['exptime'].values
        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1
        window = cmdKeys['window'].values if 'window' in cmdKeys else False

        job = self.resourceManager.request(cmd, spsSequence.DomeFlat)
        job.instantiate(cmd, exptime=exptime, duplicate=duplicate, window=window, **seqKwargs)

        job.fire(cmd)

    def domeArc(self, cmd):
        """
        `iic domeArc exptime=??? [cam=???] [arm=???] [sm=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"] [@doTest]`

        Check focus and take a set of arcs, this sequence rely on an external illuminator.
        Sequence is referenced in opdb as iic_sequence.seqtype=domeArc.
        Note that if the exposure is windowed, the seqtype will actually be domeArc_windowed.

        Parameters
        ---------
        exptime : `float`
            exposure time.
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
        """
        cmdKeys = cmd.cmd.keywords

        seqKwargs = iicUtils.genSequenceKwargs(cmd, customMade=False)
        exptime = cmdKeys['exptime'].values
        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1

        job = self.resourceManager.request(cmd, spsSequence.DomeArc)
        job.instantiate(cmd, exptime=exptime, duplicate=duplicate, **seqKwargs)

        job.fire(cmd)

    def startExposures(self, cmd):
        """
        `iic sps @startExposures exptime=??? [cam=???] [arm=???] [sm=???] [name=\"SSS\"] [comments=\"SSS\"] [@doBias] [@doTest]`

        Start object exposure loop with a given exposure time, don't stop until finishExposure.

        Parameters
        ---------
        exptime : `float`
            exposure time.
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
        doBias : `bool`
            Take interleaved bias between object.
        doTest : `bool`
           image/exposure type will be labelled as test, default=object.
        """
        cmdKeys = cmd.cmd.keywords

        seqKwargs = iicUtils.genSequenceKwargs(cmd, customMade=False)
        exptime = cmdKeys['exptime'].values[0]
        objectLoop = spsSequence.ObjectInterleavedBiasLoop if 'doBias' in cmdKeys else spsSequence.ObjectLoop

        job = self.resourceManager.request(cmd, objectLoop)
        job.instantiate(cmd, exptime=exptime, **seqKwargs)

        cmd.finish()
        job.fire(cmd=self.actor.bcast)

    def doBias(self, cmd):
        """
        `iic bias [cam=???] [arm=???] [sm=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"] [@doTest]
        [head=???] [tail=???]`

        Take a set of biases.
        Sequence is referenced in opdb as iic_sequence.seqtype=biases.

        Parameters
        ---------

        cam : list of `str`
           List of camera to expose, default=all
        arm : list of `str`
           List of arm to expose, default=all
        sm : list of `int`
           List of spectrograph module to expose, default=all
        duplicate : `int`
           Number of biases, default=15
        name : `str`
           To be inserted in opdb:iic_sequence.name.
        comments : `str`
           To be inserted in opdb:iic_sequence.comments.
        doTest : `bool`
           image/exposure type will be labelled as test, default=bias.
        head : list of `str`
            list of command to be launched before the sequence.
        tail : list of `str`
            list of command to be launched after the sequence.
        """
        cmdKeys = cmd.cmd.keywords

        seqKwargs = iicUtils.genSequenceKwargs(cmd, customMade=True)
        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1

        job = self.resourceManager.request(cmd, spsSequence.Biases)
        job.instantiate(cmd, duplicate=duplicate, **seqKwargs)

        job.fire(cmd)

    def doDark(self, cmd):
        """
        `iic dark exptime=??? [cam=???] [arm=???] [sm=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"] [@doTest]
        [head=???] [tail=???]`

        Take a set of darks with given exptime.
        Sequence is referenced in opdb as iic_sequence.seqtype=darks.

        Parameters
        ---------
        exptime : `float`
            dark exposure time.
        cam : list of `str`
           List of camera to expose, default=all
        arm : list of `str`
           List of arm to expose, default=all
        sm : list of `int`
           List of spectrograph module to expose, default=all
        duplicate : `int`
           Number of darks, default=15
        name : `str`
           To be inserted in opdb:iic_sequence.name.
        comments : `str`
           To be inserted in opdb:iic_sequence.comments.
        doTest : `bool`
           image/exposure type will be labelled as test, default=dark.
        head : list of `str`
            list of command to be launched before the sequence.
        tail : list of `str`
            list of command to be launched after the sequence.
        """
        cmdKeys = cmd.cmd.keywords

        seqKwargs = iicUtils.genSequenceKwargs(cmd, customMade=True)
        exptime = cmdKeys['exptime'].values
        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1

        job = self.resourceManager.request(cmd, spsSequence.Darks)
        job.instantiate(cmd, exptime=exptime, duplicate=duplicate, **seqKwargs)

        job.fire(cmd)

    def doArc(self, cmd):
        """
        `iic expose arc [hgar=FF.F] [hgcd=FF.F] [argon=FF.F] [neon=FF.F] [krypton=FF.F] [xenon=FF.F] [@doShutterTiming]
        [cam=???] [arm=???] [sm=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"] [@doTest] [head=???] [tail=???]`

        Take a set of arc exposure.
        Sequence is referenced in opdb as iic_sequence.seqtype=arcs.

        Parameters
        ---------
        hgar : `float`
            number of second to trigger mercury-argon lamp.
        hgcd : `float`
            number of second to trigger mercury-cadmium lamp.
        argon : `float`
            number of second to trigger argon lamp.
        neon : `float`
            number of second to trigger neon lamp.
        krypton : `float`
            number of second to trigger krypton lamp.
        xenon : `float`
            number of second to trigger xenon lamp.
        doShutterTiming : `bool`
           if True, use the shutters to control exposure time, ie fire the lamps before opening the shutters.
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
        exptime = timedLampsKwargs(cmdKeys)
        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1

        job = self.resourceManager.request(cmd, timedSpsSequence.Arcs)
        job.instantiate(cmd, exptime=exptime, dcbOn=dict(), dcbOff=dict(), duplicate=duplicate, **seqKwargs)
        job.fire(cmd)

    def doFlat(self, cmd):
        """
        `iic expose flat halogen=FF.F [window=???] [cam=???] [arm=???] [sm=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"]
        [@doTest] [head=???] [tail=???]`

        Take a set of flat exposure.
        Sequence is referenced in opdb as iic_sequence.seqtype=flats.

        Parameters
        ---------
        halogen : `float`
            number of second to trigger continuum lamp.
        window : `int`,`int`
            first row, total number of rows.
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
        exptime = timedLampsKwargs(cmdKeys)
        window = cmdKeys['window'].values if 'window' in cmdKeys else False

        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1

        job = self.resourceManager.request(cmd, timedSpsSequence.Flats)
        job.instantiate(cmd, exptime=exptime, dcbOn=dict(), dcbOff=dict(), duplicate=duplicate, window=window,
                        **seqKwargs)
        job.fire(cmd)

    def ditheredArcs(self, cmd):
        """
        `iic dither arc [hgar=FF.F] [hgcd=FF.F] [argon=FF.F] [neon=FF.F] [krypton=FF.F] [xenon=FF.F] [@doShutterTiming]
        pixels=FF.F [doMinus] [cam=???] [arm=???] sm=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"] [@doTest]
        [head=???] [tail=???]`

        Take a set of dithered Arc with a given pixel step.
        default step is set to 0.5 pixels -> 4 positions(dither_x, dither_y) = [(0,0), (0.5,0), (0, 0.5), (0.5, 0.5)].
        Sequence is referenced in opdb as iic_sequence.seqtype=ditheredArcs.

        Parameters
        ---------
        hgar : `float`
            number of second to trigger mercury-argon lamp.
        hgcd : `float`
            number of second to trigger mercury-cadmium lamp.
        argon : `float`
            number of second to trigger argon lamp.
        neon : `float`
            number of second to trigger neon lamp.
        krypton : `float`
            number of second to trigger krypton lamp.
        xenon : `float`
            number of second to trigger xenon lamp.
        doShutterTiming : `bool`
           if True, use the shutters to control exposure time, ie fire the lamps before opening the shutters.
        pixels : `float`
            dithering step in pixels.
        doMinus : `bool`
           if True, add negative dither step in the position grid.
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
        exptime = timedLampsKwargs(cmdKeys)
        pixels = cmdKeys['pixels'].values[0]
        doMinus = 'doMinus' in cmdKeys
        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1

        job = self.resourceManager.request(cmd, timedSpsSequence.DitheredArcs)
        job.instantiate(cmd, exptime=exptime, pixels=pixels, doMinus=doMinus, dcbOn=dict(), dcbOff=dict(),
                        duplicate=duplicate, **seqKwargs)
        job.fire(cmd)

    def defocusedArcs(self, cmd):
        """
        `iic defocus arc [hgar=FF.F] [hgcd=FF.F] [argon=FF.F] [neon=FF.F] [krypton=FF.F] [xenon=FF.F]
        [@doShutterTiming] position=??? [cam=???] [arm=???] [sm=???] [duplicate=N] [name=\"SSS\"]
        [comments=\"SSS\"] [@doTest] [head=???] [tail=???]`

        Take Arc dataset through focus using fca hexapod, exposure time is scaled such as psf max flux ~= constant
        Sequence is referenced in opdb as iic_sequence.seqtype=defocusedArcs.

        Parameters
        ---------
        hgar : `float`
            number of second to trigger mercury-argon lamp.
        hgcd : `float`
            number of second to trigger mercury-cadmium lamp.
        argon : `float`
            number of second to trigger argon lamp.
        neon : `float`
            number of second to trigger neon lamp.
        krypton : `float`
            number of second to trigger krypton lamp.
        xenon : `float`
            number of second to trigger xenon lamp.
        doShutterTiming : `bool`
           if True, use the shutters to control exposure time, ie fire the lamps before opening the shutters.
        position: `float`, `float`, `int`
            fca hexapod position constructor, same logic as np.linspace(start, stop, num).
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
        exptime = timedLampsKwargs(cmdKeys)
        start, stop, num = cmdKeys['position'].values
        positions = np.linspace(start, stop, num=int(num)).round(6)
        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1

        job = self.resourceManager.request(cmd, timedSpsSequence.DefocusedArcs)
        job.instantiate(cmd, exp_time_0=exptime, positions=positions, dcbOn=dict(), dcbOff=dict(), duplicate=duplicate,
                        **seqKwargs)
        job.fire(cmd)

    def hexapodStability(self, cmd):
        """
        `iic test hexapodStability [hgar=FF.F] [hgcd=FF.F] [argon=FF.F] [neon=FF.F] [krypton=FF.F] [xenon=FF.F]
        [@doShutterTiming] [position=???] [cam=???] [arm=???] [sm=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"]
        [@doTest]`

        Acquire hexapod stability grid. By default 12x12 and 3 duplicates at each position.

        Parameters
        ---------
        hgar : `float`
            number of second to trigger mercury-argon lamp.
        hgcd : `float`
            number of second to trigger mercury-cadmium lamp.
        argon : `float`
            number of second to trigger argon lamp.
        neon : `float`
            number of second to trigger neon lamp.
        krypton : `float`
            number of second to trigger krypton lamp.
        xenon : `float`
            number of second to trigger xenon lamp.
        doShutterTiming : `bool`
           if True, use the shutters to control exposure time, ie fire the lamps before opening the shutters.
        position: `float`, `float`, `int`
            fca hexapod position constructor, same logic as np.arange(start, stop, step).
        cam : list of `str`
           List of camera to expose, default=all
        arm : list of `str`
           List of arm to expose, default=all
        sm : list of `int`
           List of spectrograph module to expose, default=all
        duplicate : `int`
           Number of exposure, default=3
        name : `str`
           To be inserted in opdb:iic_sequence.name.
        comments : `str`
           To be inserted in opdb:iic_sequence.comments.
        doTest : `bool`
           image/exposure type will be labelled as test, default=arc.
        """
        cmdKeys = cmd.cmd.keywords
        seqKwargs = iicUtils.genSequenceKwargs(cmd, customMade=True)
        timedLamps = timedLampsKwargs(cmdKeys)

        duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 3
        position = cmdKeys['position'].values if 'position' in cmdKeys else [-0.05, 0.055, 0.01]
        position = np.arange(*position)

        job = self.resourceManager.request(cmd, timedSpsSequence.HexapodStability)
        job.instantiate(cmd, position=position, timedLamps=timedLamps, duplicate=duplicate, **seqKwargs)
        job.fire(cmd)

    def rdaMove(self, cmd):
        """
        `iic sps rdaMove low|med [sm=???]`

        Move Red disperser assembly to required position (low or med).

        Parameters
        ---------
        sm : list of `int`
           List of spectrograph module to expose, default=all
        """
        cmdKeys = cmd.cmd.keywords

        if 'low' in cmdKeys:
            seqObj = engineering.RdaLow
        elif 'med' in cmdKeys:
            seqObj = engineering.RdaMed
        else:
            raise ValueError('incorrect target position')

        job = self.resourceManager.request(cmd, seqObj)
        job.instantiate(cmd)
        job.fire(cmd)

    def setGratingToDesign(self, cmd):
        """
        `iic setGratingToDesign`

        Move Red disperser assembly to PfsDesign position (low or med).
        """
        if self.actor.visitor.activeField:
            position = self.actor.visitor.activeField.getGratingPosition()
        else:
            cmd.fail('text="no current pfsDesign..."')
            return

        if position == 'low':
            seqObj = engineering.RdaLow
        elif position == 'med':
            seqObj = engineering.RdaMed
        else:
            cmd.finish('text="no position requested, finishing here..."')
            return

        job = self.resourceManager.request(cmd, seqObj)
        job.instantiate(cmd)
        job.fire(cmd)
