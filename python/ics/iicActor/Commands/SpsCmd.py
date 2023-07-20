from importlib import reload

import ics.iicActor.sequenceList.sps.base as base
import ics.iicActor.sequenceList.sps.calib as calib
import ics.iicActor.sequenceList.sps.engineering as eng
import ics.iicActor.sequenceList.sps.science as science
import ics.iicActor.utils.translate as translate
import opscore.protocols.keys as keys
import opscore.protocols.types as types
from iicActor.utils.engine import ExecMode

reload(base)
reload(calib)
reload(science)
reload(eng)


class SpsCmd(object):

    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor
        identArgs = '[<cam>] [<arm>] [<specNum>]'
        commonArgs = f'{identArgs} [<duplicate>] {translate.seqArgs}'
        timedArcArgs = '[<hgar>] [<hgcd>] [<argon>] [<neon>] [<krypton>] [<xenon>] [@doShutterTiming]'
        timedFlatArgs = '[<halogen>] [@doShutterTiming]'
        windowingArgs = '[<window>] [<blueWindow>] [<redWindow>]'

        self.vocab = [
            ('masterBiases', f'{commonArgs}', self.masterBiases),
            ('masterDarks', f'[<exptime>] {commonArgs}', self.masterDarks),
            ('ditheredFlats', f'{timedFlatArgs} [<pixelRange>] [<interleaveDark>] {commonArgs}', self.ditheredFlats),
            ('scienceArc', f'{timedArcArgs} {commonArgs}', self.scienceArc),
            ('scienceTrace', f'{timedFlatArgs} {windowingArgs} {commonArgs}', self.scienceTrace),
            ('domeFlat', f'<exptime> {windowingArgs} {commonArgs}', self.domeFlat),
            ('scienceObject', f'<exptime> {windowingArgs} {commonArgs}', self.scienceObject),

            ('sps', f'@startExposures <exptime> {windowingArgs} {commonArgs}', self.startExposureLoop),
            ('sps', f'@erase {commonArgs}', self.erase),

            ('bias', f'{commonArgs}', self.doBias),
            ('dark', f'<exptime> {commonArgs}', self.doDark),
            ('expose', f'arc {timedArcArgs} {commonArgs}', self.doArc),
            ('expose', f'flat {timedFlatArgs} {windowingArgs} {commonArgs}', self.doFlat),

            ('ditheredArcs', f'{timedArcArgs} <pixelStep> {commonArgs}', self.ditheredArcs),
            ('defocusedArcs', f'{timedArcArgs} <position> {commonArgs}', self.defocusedArcs),
            ('fpa', f'throughfocus <micronsRange> {timedArcArgs} {commonArgs}', self.fpaThroughFocus),
            ('test', f'hexapodStability {timedArcArgs} [<position>] {commonArgs}', self.hexapodStability),

            ('sps', 'rdaMove (low|med) [<specNum>]', self.rdaMove),
            ('setGratingToDesign', '', self.setGratingToDesign),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary('iic_sps', (1, 1),
                                        keys.Key('exptime', types.Float() * (1,), help='exptime list (seconds)'),
                                        keys.Key('duplicate', types.Int(), help='exposure duplicate (1 is default)'),
                                        keys.Key('cam', types.String() * (1,), help='camera(s) to take exposure from'),
                                        keys.Key('arm', types.String() * (1,), help='arm to take exposure from'),
                                        keys.Key('specNum', types.Int() * (1,),
                                                 help='spectrograph module(s) to take exposure from'),
                                        keys.Key('name', types.String(), help='iic_sequence name'),
                                        keys.Key('comments', types.String(), help='iic_sequence comments'),
                                        keys.Key('groupId', types.Int(), help='optional groupId'),
                                        keys.Key('head', types.String() * (1,), help='cmdStr list to process before'),
                                        keys.Key('tail', types.String() * (1,), help='cmdStr list to process after'),

                                        keys.Key('halogen', types.Float(), help='quartz halogen lamp on time'),
                                        keys.Key('argon', types.Float(), help='Ar lamp on time'),
                                        keys.Key('hgar', types.Float(), help='HgAr lamp on time'),
                                        keys.Key('neon', types.Float(), help='Ne lamp on time'),
                                        keys.Key('krypton', types.Float(), help='Kr lamp on time'),
                                        keys.Key('hgcd', types.Float(), help='HgCd lamp on time'),
                                        keys.Key('xenon', types.Float(), help='Xenon lamp on time'),

                                        keys.Key('pixelRange', types.Float() * (1, 3),
                                                 help='pixels array(start, stop, step) for ditheredFlats'
                                                      'default(-6,6,0.3)'),
                                        keys.Key('pixelStep', types.Float(),
                                                 help='pixel step for ditheredArcs'),
                                        keys.Key('position', types.Float() * (1, 3),
                                                 help='slit position(start, stop, step) for defocusedArcs'),
                                        keys.Key('micronsRange', types.Float() * (1, 3),
                                                 help='fpa range from focus(start, stop, nPosition)'),

                                        keys.Key("window", types.Int() * (1, 2),
                                                 help='first row, total number of rows to read'),
                                        keys.Key("blueWindow", types.Int() * (1, 2),
                                                 help='first row, total number of rows to read'),
                                        keys.Key("redWindow", types.Int() * (1, 2),
                                                 help='first row, total number of rows to read'),
                                        keys.Key('interleaveDark', types.Float(),
                                                 help='darkTime for interleaved darks)'),
                                        )

    @property
    def engine(self):
        return self.actor.engine

    def masterBiases(self, cmd):
        """
        `iic masterBiases [cam=???] [arm=???] [specNum=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"] [@doTest]`

        Take a set of biases.
        Sequence is referenced in opdb as iic_sequence.seqtype=masterBiases.

        Parameters
        ---------

        cam : list of `str`
           List of camera to expose, default=all
        arm : list of `str`
           List of arm to expose, default=all
        specNum : list of `int`
           List of spectrograph module to expose, default=all
        duplicate : `int`
           Number of biases, default=15
        name : `str`
           To be inserted in opdb:iic_sequence.name.
        comments : `str`
           To be inserted in opdb:iic_sequence.comments.
        doTest : `bool`
           image/exposure type will be labelled as test, default=bias.
        groupId : `int`
           optional sequence group id.
        """
        cmdKeys = cmd.cmd.keywords

        masterBiases = calib.MasterBiases.fromCmdKeys(self.actor, cmdKeys)
        self.engine.runInThread(cmd, masterBiases)

    def masterDarks(self, cmd):
        """
        `iic masterDarks [exptime=???] [cam=???] [arm=???] [specNum=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"] [@doTest]`

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
        specNum : list of `int`
           List of spectrograph module to expose, default=all
        duplicate : `int`
           Number of darks, default=15
        name : `str`
           To be inserted in opdb:iic_sequence.name.
        comments : `str`
           To be inserted in opdb:iic_sequence.comments.
        doTest : `bool`
           image/exposure type will be labelled as test, default=dark.
        groupId : `int`
           optional sequence group id.
        """
        cmdKeys = cmd.cmd.keywords

        masterDarks = calib.MasterDarks.fromCmdKeys(self.actor, cmdKeys)
        self.engine.runInThread(cmd, masterDarks)

    def ditheredFlats(self, cmd):
        """
        `iic ditheredFlats halogen=FF.F [@doShutterTiming] [pixels=FF.F,FF.F,FF.F] [cam=???] [arm=???] [specNum=???]
        [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"] [@doTest]`

        Take a set of dithered fiberTrace with a given pixel step (default=0.3).
        Sequence is referenced in opdb as iic_sequence.seqtype=ditheredFlats.

        Parameters
        ---------
        halogen : `float`
            number of second to trigger continuum lamp.
        doShutterTiming : `bool`
           if True, use the shutters to control exposure time, ie fire the lamps before opening the shutters.
        pixels : `float`,`float`,`float`
            pixels array : start, end, step (default: -6, 6, 0.3).
        cam : list of `str`
           List of camera to expose, default=all.
        arm : list of `str`
           List of arm to expose, default=all.
        specNum : list of `int`
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

        ditheredFlats = calib.DitheredFlats.fromCmdKeys(self.actor, cmdKeys)
        self.engine.runInThread(cmd, ditheredFlats)

    def scienceArc(self, cmd):
        """
        `iic scienceArc [hgar=FF.F] [hgcd=FF.F] [argon=FF.F] [neon=FF.F] [krypton=FF.F] [xenon=FF.F] [@doShutterTiming]
        [cam=???] [arm=???] [specNum=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"] [@doTest]`

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
        specNum : list of `int`
           List of spectrograph module to expose, default=all
        duplicate : `int`
           Number of exposure, default=1
        name : `str`
           To be inserted in opdb:iic_sequence.name.
        comments : `str`
           To be inserted in opdb:iic_sequence.comments.
        doTest : `bool`
           image/exposure type will be labelled as test, default=arc
        groupId : `int`
           optional sequence group id.
        """
        cmdKeys = cmd.cmd.keywords

        scienceArc = calib.ScienceArc.fromCmdKeys(self.actor, cmdKeys)
        self.engine.runInThread(cmd, scienceArc)

    def scienceTrace(self, cmd):
        """
        `iic scienceTrace halogen=FF.F [@doShutterTiming] [window=???] [blueWindow=???] [redWindow=???] [cam=???]
        [arm=???] [specNum=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"] [@doTest]`

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
        blueWindow : `int`,`int`
            first row, total number of rows. (blue arm)
        redWindow : `int`,`int`
            first row, total number of rows. (red arm)
        cam : list of `str`
           List of camera to expose, default=all
        arm : list of `str`
           List of arm to expose, default=all
        specNum : list of `int`
           List of spectrograph module to expose, default=all
        duplicate : `int`
           Number of exposure, default=1
        name : `str`
           To be inserted in opdb:iic_sequence.name.
        comments : `str`
           To be inserted in opdb:iic_sequence.comments.
        doTest : `bool`
           image/exposure type will be labelled as test, default=flat.
        groupId : `int`
           optional sequence group id.
        """
        cmdKeys = cmd.cmd.keywords

        scienceTrace = calib.ScienceTrace.fromCmdKeys(self.actor, cmdKeys)
        self.engine.runInThread(cmd, scienceTrace)

    def domeFlat(self, cmd):
        """
        `iic domeFlat exptime=??? [window=???] [blueWindow=???] [redWindow=???] [cam=???] [arm=???] [specNum=???]
         [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"] [@doTest]`

        Check focus and take a set of fiberTrace, this sequence rely on an external illuminator (HSC lamps).
        Sequence is referenced in opdb as iic_sequence.seqtype=domeFlat.
        Note that if the exposure is windowed, the seqtype will actually be domeFlat_windowed.

        Parameters
        ---------
        exptime : `float`
            exposure time.
        window : `int`,`int`
            first row, total number of rows.
        blueWindow : `int`,`int`
            first row, total number of rows. (blue arm)
        redWindow : `int`,`int`
            first row, total number of rows. (red arm)
        cam : list of `str`
           List of camera to expose, default=all
        arm : list of `str`
           List of arm to expose, default=all
        specNum : list of `int`
           List of spectrograph module to expose, default=all
        duplicate : `int`
           Number of exposure, default=1
        name : `str`
           To be inserted in opdb:iic_sequence.name.
        comments : `str`
           To be inserted in opdb:iic_sequence.comments.
        doTest : `bool`
           image/exposure type will be labelled as test, default=domeflat.
        groupId : `int`
           optional sequence group id.
        """
        cmdKeys = cmd.cmd.keywords

        domeFlat = calib.DomeFlat.fromCmdKeys(self.actor, cmdKeys)
        self.engine.runInThread(cmd, domeFlat)

    def scienceObject(self, cmd):
        """
        `iic scienceObject exptime=??? [window=???] [blueWindow=???] [redWindow=???] [cam=???] [arm=???] [specNum=???]
        [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"] [@doTest]`

        Check focus and take a set of object exposure.
        Sequence is referenced in opdb as iic_sequence.seqtype=scienceObject.
        Note that if the exposure is windowed, the seqtype will actually be scienceObject_windowed.

        Parameters
        ---------
        exptime : `float`
            exposure time.
        window : `int`,`int`
            first row, total number of rows.
        blueWindow : `int`,`int`
            first row, total number of rows. (blue arm)
        redWindow : `int`,`int`
            first row, total number of rows. (red arm)
        cam : list of `str`
           List of camera to expose, default=all
        arm : list of `str`
           List of arm to expose, default=all
        specNum : list of `int`
           List of spectrograph module to expose, default=all
        duplicate : `int`
           Number of exposure, default=1
        name : `str`
           To be inserted in opdb:iic_sequence.name.
        comments : `str`
           To be inserted in opdb:iic_sequence.comments.
        doTest : `bool`
           image/exposure type will be labelled as test, default=object.
        groupId : `int`
           optional sequence group id.
        """
        cmdKeys = cmd.cmd.keywords

        scienceObject = science.ScienceObject.fromCmdKeys(self.actor, cmdKeys)
        self.engine.runInThread(cmd, scienceObject)

    def startExposureLoop(self, cmd):
        """
        `iic sps @startExposures exptime=??? [cam=???] [arm=???] [specNum=???] [name=\"SSS\"] [comments=\"SSS\"] [@doBias] [@doTest]`

        Start object exposure loop with a given exposure time, don't stop until finishExposure.

        Parameters
        ---------
        exptime : `float`
            exposure time.
        cam : list of `str`
           List of camera to expose, default=all
        arm : list of `str`
           List of arm to expose, default=all
        specNum : list of `int`
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
        groupId : `int`
           optional sequence group id.
        """
        cmdKeys = cmd.cmd.keywords

        exposureLoop = science.ScienceObjectLoop.fromCmdKeys(self.actor, cmdKeys)
        # Check if resources are available, prepare sequence to be executed but do not fire *anything* yet.
        self.engine.run(cmd, exposureLoop, mode=ExecMode.CHECKIN, doFinish=False)
        # Sequence has been rejected, no need to go further.
        if not cmd.alive:
            return

        # Returning command right away.
        cmd.finish()
        # Running sequence in background.
        self.engine.runInThread(self.actor.bcast, exposureLoop, mode=ExecMode.CONCLUDE)

    def erase(self, cmd):
        """
        `iic sps erase [cam=???] [arm=???] [specNum=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"]`

        Erase sps detectors, meant mainly to use before windowed exposures.

        Parameters
        ---------
        cam : list of `str`
           List of camera to erase, default=all
        arm : list of `str`
           List of arm to erase, default=all
        specNum : list of `int`
           List of spectrograph module to erase, default=all
        duplicate : `int`
           Number of repeat, default=1
        name : `str`
           To be inserted in opdb:iic_sequence.name.
        comments : `str`
           To be inserted in opdb:iic_sequence.comments.
        groupId : `int`
           optional sequence group id.
        """
        cmdKeys = cmd.cmd.keywords

        erase = base.Erase.fromCmdKeys(self.actor, cmdKeys)
        self.engine.runInThread(cmd, erase)

    def doBias(self, cmd):
        """
        `iic bias [cam=???] [arm=???] [specNum=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"] [@doTest]
        [head=???] [tail=???]`

        Take a set of biases.
        Sequence is referenced in opdb as iic_sequence.seqtype=biases.

        Parameters
        ---------

        cam : list of `str`
           List of camera to expose, default=all
        arm : list of `str`
           List of arm to expose, default=all
        specNum : list of `int`
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
        groupId : `int`
           optional sequence group id.
        """
        cmdKeys = cmd.cmd.keywords

        biases = base.Biases.fromCmdKeys(self.actor, cmdKeys)
        self.engine.runInThread(cmd, biases)

    def doDark(self, cmd):
        """
        `iic dark exptime=??? [cam=???] [arm=???] [specNum=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"] [@doTest]
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
        specNum : list of `int`
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
        groupId : `int`
           optional sequence group id.
        """
        cmdKeys = cmd.cmd.keywords

        darks = base.Darks.fromCmdKeys(self.actor, cmdKeys)
        self.engine.runInThread(cmd, darks)

    def doArc(self, cmd):
        """
        `iic expose arc [hgar=FF.F] [hgcd=FF.F] [argon=FF.F] [neon=FF.F] [krypton=FF.F] [xenon=FF.F] [@doShutterTiming]
        [cam=???] [arm=???] [specNum=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"] [@doTest] [head=???] [tail=???]`

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
        specNum : list of `int`
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
        groupId : `int`
           optional sequence group id.
        """
        cmdKeys = cmd.cmd.keywords

        arcs = base.Arcs.fromCmdKeys(self.actor, cmdKeys)
        self.engine.runInThread(cmd, arcs)

    def doFlat(self, cmd):
        """
        `iic expose flat halogen=FF.F [window=???] [cam=???] [arm=???] [specNum=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"]
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
        specNum : list of `int`
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
        groupId : `int`
           optional sequence group id.
        """
        cmdKeys = cmd.cmd.keywords

        flats = base.Flats.fromCmdKeys(self.actor, cmdKeys)
        self.engine.runInThread(cmd, flats)

    def ditheredArcs(self, cmd):
        """
        `iic dither arc [hgar=FF.F] [hgcd=FF.F] [argon=FF.F] [neon=FF.F] [krypton=FF.F] [xenon=FF.F] [@doShutterTiming]
        pixels=FF.F [doMinus] [cam=???] [arm=???] specNum=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"] [@doTest]
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
        specNum : list of `int`
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
        groupId : `int`
           optional sequence group id.
        """
        cmdKeys = cmd.cmd.keywords

        ditheredArcs = base.DitheredArcs.fromCmdKeys(self.actor, cmdKeys)
        self.engine.runInThread(cmd, ditheredArcs)

    def defocusedArcs(self, cmd):
        """
        `iic defocus arc [hgar=FF.F] [hgcd=FF.F] [argon=FF.F] [neon=FF.F] [krypton=FF.F] [xenon=FF.F]
        [@doShutterTiming] position=??? [cam=???] [arm=???] [specNum=???] [duplicate=N] [name=\"SSS\"]
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
        specNum : list of `int`
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
        groupId : `int`
           optional sequence group id.
        """
        cmdKeys = cmd.cmd.keywords

        defocusedArcs = base.DefocusedArcs.fromCmdKeys(self.actor, cmdKeys)
        self.engine.runInThread(cmd, defocusedArcs)

    def fpaThroughFocus(self, cmd):
        """
        `iic fpaThroughFocus [hgar=FF.F] [hgcd=FF.F] [argon=FF.F] [neon=FF.F] [krypton=FF.F] [xenon=FF.F]
        [@doShutterTiming] micronsRange=??? [cam=???] [arm=???] [specNum=???] [duplicate=N] [name=\"SSS\"]
        [comments=\"SSS\"] [@doTest] [head=???] [tail=???]`

        Take Arc dataset through focus, with respect to tilt, using fpa motors.
        Sequence is referenced in opdb as iic_sequence.seqtype=fpaThroughFocus.

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
        micronsRange: `float`, `float`, `int`
            fpa position constructor, same logic as np.linspace(start, stop, num).
        cam : list of `str`
           List of camera to expose, default=all
        arm : list of `str`
           List of arm to expose, default=all
        specNum : list of `int`
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
        groupId : `int`
           optional sequence group id.
        """
        cmdKeys = cmd.cmd.keywords

        fpaThroughFocus = base.FpaThroughFocus.fromCmdKeys(self.actor, cmdKeys)
        self.engine.runInThread(cmd, fpaThroughFocus)

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
        groupId : `int`
           optional sequence group id.
        """
        cmdKeys = cmd.cmd.keywords

        hexapodStability = eng.HexapodStability.fromCmdKeys(self.actor, cmdKeys)
        self.engine.runInThread(cmd, hexapodStability)

    def rdaMove(self, cmd):
        """
        `iic sps rdaMove low|med [specNum=???]`

        Move Red disperser assembly to required position (low or med).

        Parameters
        ---------
        sm : list of `int`
           List of spectrograph module to expose, default=all
        """
        cmdKeys = cmd.cmd.keywords

        rdaMove = eng.RdaMove.fromCmdKeys(self.actor, cmdKeys)
        self.engine.runInThread(cmd, rdaMove)

    def setGratingToDesign(self, cmd):
        """
        `iic setGratingToDesign`

        Move Red disperser assembly to PfsDesign position (low or med).
        """
        if self.engine.visitManager.activeField:
            targetPosition = self.engine.visitManager.activeField.getGratingPosition()
        else:
            cmd.fail('text="no current pfsDesign..."')
            return

        if targetPosition is None:
            cmd.finish('text="no grating position requested, finishing here..."')
            return

        rdaMove = eng.RdaMove.fromDesign(self.actor, targetPosition)
        self.engine.runInThread(cmd, rdaMove)
