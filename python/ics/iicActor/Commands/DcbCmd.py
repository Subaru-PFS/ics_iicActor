from importlib import reload

import ics.iicActor.sequenceList.sps.dcb as dcb
import ics.iicActor.utils.translate as translate
import opscore.protocols.keys as keys
import opscore.protocols.types as types

reload(dcb)


class DcbCmd(object):

    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor
        identArgs = '[<cam>] [<arm>] [<specNum>]'
        commonArgs = f'{identArgs} [<duplicate>] {translate.seqArgs}'
        arcArgs = f'<exptime> [<switchOn>] [<switchOff>] [<warmingTime>] [force]'
        flatArgs = f'<exptime> [noLampCtl] [switchOff] [<warmingTime>] [force]'
        windowingArgs = '[<window>] [<blueWindow>] [<redWindow>]'

        self.vocab = [
            ('ditheredFlats', f'{flatArgs} [<pixelRange>] {commonArgs}', self.ditheredFlats),
            ('scienceArc', f'{arcArgs} {commonArgs}', self.scienceArc),
            ('scienceTrace', f'{flatArgs} {windowingArgs} {commonArgs}', self.scienceTrace),

            ('expose', f'arc {arcArgs} {commonArgs}', self.doArc),
            ('expose', f'flat {flatArgs} {windowingArgs} {commonArgs}', self.doFlat),

            ('detector', f'throughfocus {arcArgs} <position> [<tilt>] {commonArgs}', self.detThroughFocus),
            ('slit', f'throughfocus {arcArgs} <position> {commonArgs}', self.slitThroughFocus),
            ('ditheredArcs', f'{arcArgs} <pixelStep> {commonArgs}', self.ditheredArcs),
            ('defocusedArcs', f'{arcArgs} <position> {commonArgs}', self.defocusedArcs),

        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary('iic_dcb', (1, 1),
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

                                        keys.Key('switchOn', types.String() * (1, None),
                                                 help='which dcb lamp to switch on.'),
                                        keys.Key('switchOff', types.String() * (1, None),
                                                 help='which dcb lamp to switch off.'),
                                        keys.Key('warmingTime', types.Float(), help='customizable warming time'),

                                        keys.Key('pixelRange', types.Float() * (1, 3),
                                                 help='pixels array(start, stop, step) for ditheredFlats'
                                                      'default(-6,6,0.3)'),
                                        keys.Key('pixelStep', types.Float(),
                                                 help='pixel step for ditheredArcs'),
                                        keys.Key('position', types.Float() * (1, 3),
                                                 help='slit/motor position for throughfocus same args as np.linspace'),
                                        keys.Key('tilt', types.Float() * (1, 3), help='motor tilt (a, b, c)'),

                                        keys.Key("window", types.Int() * (1, 2),
                                                 help='first row, total number of rows to read'),
                                        keys.Key("blueWindow", types.Int() * (1, 2),
                                                 help='first row, total number of rows to read'),
                                        keys.Key("redWindow", types.Int() * (1, 2),
                                                 help='first row, total number of rows to read'),
                                        )

    @property
    def engine(self):
        return self.actor.engine

    def ditheredFlats(self, cmd):
        """
        `iic ditheredFlats exptime=??? [pixelRange=FF.F,FF.F,FF.F] [warmingTime=FF.F] [force] [noLampCtl] [switchOff]
        [cam=???] [arm=???] [specNum=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"] [@doTest] [head=???] [tail=???]`

        Take a set of dithered fiberTrace with a given pixel step (default=0.3).
        Sequence is referenced in opdb as iic_sequence.seqtype=ditheredFlats.

        Parameters
        ---------
        exptime : `float`
            shutter exposure time.
        pixelRange : `float`,`float`,`float`
            pixels array : start, end, step (default: -6, 6, 0.3).
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
        head : list of `str`
            list of command to be launched before the sequence.
        tail : list of `str`
            list of command to be launched after the sequence.
        """
        cmdKeys = cmd.cmd.keywords

        ditheredFlats = dcb.DitheredFlats.fromCmdKeys(self.actor, cmdKeys)
        self.engine.runInThread(cmd, ditheredFlats)

    def scienceArc(self, cmd):
        """
        `iic scienceArc exptime=??? [switchOn=???] [switchOff=???] [warmingTime=FF.F] [force]
         [cam=???] [arm=???] [specNum=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"] [@doTest]`

        Check focus and take a set of arc exposure.
        Sequence is referenced in opdb as iic_sequence.seqtype=scienceArc.

        Parameters
        ---------
         exptime : `float`
            shutter exposure time.
        switchOn : list of `str`
           list of dcb lamp to turn on before the exposure(s).
        switchOff : list of `str`
           list of dcb lamp to turn off after the exposure(s).
        warmingTime : `float`
            optional lamp warming time.
        force : `bool`
            skip any lamp warmup logic.
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

        scienceArc = dcb.ScienceArc.fromCmdKeys(self.actor, cmdKeys)
        self.engine.runInThread(cmd, scienceArc)

    def scienceTrace(self, cmd):
        """
        `iic scienceTrace exptime=FF.F [warmingTime=FF.F] [force] [noLampCtl] [switchOff] [window=???] [blueWindow=???]
        [redWindow=???] [cam=???] [arm=???] [specNum=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"] [@doTest]`

        Check focus and take a set of fiberTrace.
        Sequence is referenced in opdb as iic_sequence.seqtype=scienceTrace.
        Note that if the exposure is windowed, the seqtype will actually be scienceTrace_windowed.

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

        scienceTrace = dcb.ScienceTrace.fromCmdKeys(self.actor, cmdKeys)
        self.engine.runInThread(cmd, scienceTrace)

    def doArc(self, cmd):
        """
        `iic expose arc exptime=??? [switchOn=???] [switchOff=???] [warmingTime=FF.F] [force] [cam=???] [arm=???]
        [specNum=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"] [@doTest] [head=???] [tail=???]`

        Take a set of arc exposure.
        Sequence is referenced in opdb as iic_sequence.seqtype=arcs.

        Parameters
        ---------
        exptime : `float`
            shutter exposure time.
        switchOn : list of `str`
           list of dcb lamp to turn on before the exposure(s).
        switchOff : list of `str`
           list of dcb lamp to turn off after the exposure(s).
        warmingTime : `float`
            optional lamp warming time.
        force : `bool`
            skip any lamp warmup logic.
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
        """
        cmdKeys = cmd.cmd.keywords

        arcs = dcb.Arcs.fromCmdKeys(self.actor, cmdKeys)
        self.engine.runInThread(cmd, arcs)

    def doFlat(self, cmd):
        """
        `iic expose flat exptime=??? [warmingTime=FF.F] [force] [noLampCtl] [switchOff] [cam=???] [arm=???] [specNum=???]
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
        """
        cmdKeys = cmd.cmd.keywords

        flats = dcb.Flats.fromCmdKeys(self.actor, cmdKeys)
        self.engine.runInThread(cmd, flats)

    def detThroughFocus(self, cmd):
        """
        `iic detector throughfocus exptime=??? position=??? [tilt=???] [switchOn=???] [switchOff=???]
        [warmingTime=FF.F] [force] [cam=???] [arm=???] [specNum=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"]
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
        switchOn : list of `str`
           list of dcb lamp to turn on before the exposure(s).
        switchOff : list of `str`
           list of dcb lamp to turn off after the exposure(s).
        warmingTime : `float`
            optional lamp warming time.
        force : `bool`
            skip any lamp warmup logic.
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
        head : list of `str`
            list of command to be launched before the sequence.
        tail : list of `str`
            list of command to be launched after the sequence.
        doTest : `bool`
           image/exposure type will be labelled as test, default=arc.
        """
        cmdKeys = cmd.cmd.keywords

        detThroughFocus = dcb.DetThroughFocus.fromCmdKeys(self.actor, cmdKeys)
        self.engine.runInThread(cmd, detThroughFocus)

    def slitThroughFocus(self, cmd):
        """
        `iic slit throughfocus exptime=??? position=??? [switchOn=???] [switchOff=???]
        [warmingTime=FF.F] [force] [cam=???] [arm=???] [specNum=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"]
        [@doTest] [head=???] [tail=???]`

        Take Arc dataset through focus using the slit hexapod .
        Sequence is referenced in opdb as iic_sequence.seqtype=slitThroughFocus.

        Parameters
        ---------
        exptime : `float`
            shutter exposure time.
        position: `float`, `float`, `int`
            slit position constructor, same logic as np.linspace(start, stop, num).
        switchOn : list of `str`
           list of dcb lamp to turn on before the exposure(s).
        switchOff : list of `str`
           list of dcb lamp to turn off after the exposure(s).
        warmingTime : `float`
            optional lamp warming time.
        force : `bool`
            skip any lamp warmup logic.
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
        head : list of `str`
            list of command to be launched before the sequence.
        tail : list of `str`
            list of command to be launched after the sequence.
        doTest : `bool`
           image/exposure type will be labelled as test, default=arc.
        """
        cmdKeys = cmd.cmd.keywords

        slitThroughFocus = dcb.SlitThroughFocus.fromCmdKeys(self.actor, cmdKeys)
        self.engine.runInThread(cmd, slitThroughFocus)

    def ditheredArcs(self, cmd):
        """
        `iic dither arc exptime=??? pixelStep=FF.F [switchOn=???] [switchOff=???] [warmingTime=FF.F] [force]
        [cam=???] [arm=???] [specNum=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"] [@doTest] [head=???] [tail=???]`

        Take a set of dithered Arc with a given pixel step.
        default step is set to 0.5 pixels -> 4 positions(dither_x, dither_y) = [(0,0), (0.5,0), (0, 0.5), (0.5, 0.5)].
        Sequence is referenced in opdb as iic_sequence.seqtype=ditheredArcs.

        Parameters
        ---------
        exptime : `float`
            shutter exposure time.
        pixelStep : `float`
            dithering step in pixels.
        switchOn : list of `str`
           list of dcb lamp to turn on before the exposure(s).
        switchOff : list of `str`
           list of dcb lamp to turn off after the exposure(s).
        warmingTime : `float`
            optional lamp warming time.
        force : `bool`
            skip any lamp warmup logic.
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
        """
        cmdKeys = cmd.cmd.keywords

        ditheredArcs = dcb.DitheredArcs.fromCmdKeys(self.actor, cmdKeys)
        self.engine.runInThread(cmd, ditheredArcs)

    def defocusedArcs(self, cmd):
        """
        `iic defocus arc exptime=??? position=??? [switchOn=???] [switchOff=???] [warmingTime=FF.F] [force] [cam=???]
        [arm=???] [specNum=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"] [@doTest] [head=???] [tail=???]`

        Take Arc dataset through focus using fca hexapod, exposure time is scaled such as psf max flux ~= constant
        Sequence is referenced in opdb as iic_sequence.seqtype=defocusedArcs.

        Parameters
        ---------
        exptime : `float`
            shutter exposure time.
        position: `float`, `float`, `int`
            fca hexapod position constructor, same logic as np.linspace(start, stop, num).
        switchOn : list of `str`
           list of dcb lamp to turn on before the exposure(s).
        switchOff : list of `str`
           list of dcb lamp to turn off after the exposure(s).
        warmingTime : `float`
            optional lamp warming time.
        force : `bool`
            skip any lamp warmup logic.
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
        """
        cmdKeys = cmd.cmd.keywords

        defocusedArcs = dcb.DefocusedArcs.fromCmdKeys(self.actor, cmdKeys)
        self.engine.runInThread(cmd, defocusedArcs)
