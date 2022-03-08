"""
commands.py
====================================
Documented IIC SPS commands
"""


class MasterBiases:
    """iic masterBiases [cam=???] [arm=???] [sm=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"] [@doTest]"""

    def __init__(self):
        """
        """
        pass

    @classmethod
    def build(cls, cam=None, arm=None, sm=None, duplicate=15, name="calibProduct", comments="", doTest=False):
        """
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
        return cls()


class MasterDarks:
    """iic masterDarks [exptime=???] [cam=???] [arm=???] [sm=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"]
    [@doTest]"""

    def __init__(self):
        """
        """
        pass

    @classmethod
    def build(cls, exptime, cam=None, arm=None, sm=None, duplicate=15, name="calibProduct", comments="", doTest=False):
        """
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
        return cls()


class ScienceObject:
    """iic scienceObject exptime=??? [window=???] [cam=???] [arm=???] [sm=???] [duplicate=N]
    [name=\"SSS\"] [comments=\"SSS\"] [@doTest]"""

    def __init__(self):
        """
        """
        pass

    @classmethod
    def build(cls, exptime, window=None, cam=None, arm=None, sm=None, duplicate=1, name="", comments="", doTest=False):
        """
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
        return cls()


class ScienceArc:
    """iic scienceArc [hgar=FF.F] [hgcd=FF.F] [argon=FF.F] [neon=FF.F] [krypton=FF.F] [xenon=FF.F] [@doShutterTiming]
    [cam=???] [arm=???] [sm=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"] [@doTest] """

    def __init__(self):
        """
        """
        pass

    @classmethod
    def build(cls, hgar=0, hgcd=0, argon=0, neon=0, krypton=0, xenon=0, doShutterTiming=False, cam=None, arm=None,
              sm=None, duplicate=1, name="", comments="", doTest=False):
        """
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
        return cls()


class ScienceTrace:
    """iic scienceTrace halogen=FF.F [@doShutterTiming] [window=???] [cam=???] [arm=???] [sm=???] [duplicate=N]
    [name=\"SSS\"] [comments=\"SSS\"] [@doTest]"""

    def __init__(self):
        """
        """
        pass

    @classmethod
    def build(cls, halogen, doShutterTiming=False, window=None, cam=None, arm=None, sm=None, duplicate=1,
              name="", comments="", doTest=False):
        """
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
        return cls()


class DomeFlat:
    """iic domeFlat exptime=??? [window=???] [cam=???] [arm=???] [sm=???] [duplicate=N] [name=\"SSS\"]
    [comments=\"SSS\"] [@doTest]"""

    def __init__(self):
        """
        """
        pass

    @classmethod
    def build(cls, exptime, window=None, cam=None, arm=None, sm=None, duplicate=1, name="",
              comments="", doTest=False):
        """
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
        return cls()


class DomeArc:
    """iic domeArc exptime=??? [cam=???] [arm=???] [sm=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"] [@doTest]"""

    def __init__(self):
        """
        """
        pass

    @classmethod
    def build(cls, exptime, cam=None, arm=None, sm=None, duplicate=1, name="", comments="", doTest=False):
        """
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
        return cls()


class DitheredFlats:
    """iic ditheredFlats halogen=FF.F [@doShutterTiming] [pixels=FF.F] [nPositions=N] [cam=???] [arm=???] [sm=???]
    [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"] [@doTest]"""

    def __init__(self):
        """
        """
        pass

    @classmethod
    def build(cls, halogen, doShutterTiming=False, pixels=0.3, nPositions=20, cam=None, arm=None, sm=None, duplicate=1,
              name="", comments="", doTest=False):
        """
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
        return cls()


class DitheredArcs:
    """iic dither arc [hgar=FF.F] [hgcd=FF.F] [argon=FF.F] [neon=FF.F] [krypton=FF.F] [xenon=FF.F] [@doShutterTiming]
     pixels=FF.F [doMinus] [cam=???] [arm=???] [sm=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"]
     [head=???] [tail=???] [@doTest]"""

    def __init__(self):
        """
        """
        pass

    @classmethod
    def build(cls, hgar=0, hgcd=0, argon=0, neon=0, krypton=0, xenon=0, doShutterTiming=False, pixels=0.5,
              doMinus=False, cam=None, arm=None, sm=None, duplicate=1, name="", comments="", head=None, tail=None,
              doTest=False):
        """
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
           if True, add negative dither step in the position combination.
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
        return cls()


class DefocusArcs:
    """iic defocus arc [hgar=FF.F] [hgcd=FF.F] [argon=FF.F] [neon=FF.F] [krypton=FF.F] [xenon=FF.F] [@doShutterTiming]
    position=??? [cam=???] [arm=???] [sm=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"] [head=???] [tail=???]
    [@doTest]"""

    def __init__(self):
        """
        """
        pass

    @classmethod
    def build(cls, hgar=0, hgcd=0, argon=0, neon=0, krypton=0, xenon=0, doShutterTiming=False, position=(-4.0, 4.0, 17),
              cam=None, arm=None, sm=None, duplicate=1, name="", comments="", head=None, tail=None, doTest=False):
        """
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
        head : list of `str`
            list of command to be launched before the sequence.
        tail : list of `str`
            list of command to be launched after the sequence.
        doTest : `bool`
           image/exposure type will be labelled as test, default=arc.
        """
        return cls()


class DetectorThroughFocus:
    """iic detector throughfocus [hgar=FF.F] [hgcd=FF.F] [argon=FF.F] [neon=FF.F] [krypton=FF.F] [xenon=FF.F]
     [@doShutterTiming] position=??? [tilt=???] [cam=???] [arm=???] [sm=???] [duplicate=N] [name=\"SSS\"]
     [comments=\"SSS\"] [head=???] [tail=???] [@doTest]"""

    def __init__(self):
        """
        """
        pass

    @classmethod
    def build(cls, hgar=0, hgcd=0, argon=0, neon=0, krypton=0, xenon=0, doShutterTiming=False, position=(0, 290, 10),
              tilt=(0, 0, 0), cam=None, arm=None, sm=None, duplicate=1, name="", comments="", head=None, tail=None,
              doTest=False):
        """
        Take Arc dataset through focus using Focal Plane Array focus motors.
        Sequence is referenced in opdb as iic_sequence.seqtype=detThroughFocus.

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
            fpa position constructor, same logic as np.linspace(start, stop, num).
        tilt: `float`, `float`, `float`
            fpa A,B,C motor tilt position.
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
        return cls()


class Biases:
    """iic bias [cam=???] [arm=???] [sm=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"] [head=???] [tail=???]
    [@doTest]"""

    def __init__(self):
        """
        """
        pass

    @classmethod
    def build(cls, cam=None, arm=None, sm=None, duplicate=1, name="", comments="", head=None, tail=None, doTest=False):
        """
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
        head : list of `str`
            list of command to be launched before the sequence.
        tail : list of `str`
            list of command to be launched after the sequence.
        doTest : `bool`
           image/exposure type will be labelled as test, default=bias.
        """
        return cls()


class Darks:
    """iic dark exptime=??? [cam=???] [arm=???] [sm=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"] [head=???]
    [tail=???] [@doTest]"""

    def __init__(self):
        """
        """
        pass

    @classmethod
    def build(cls, exptime, cam=None, arm=None, sm=None, duplicate=1, name="", comments="", head=None, tail=None,
              doTest=False):
        """
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
        head : list of `str`
            list of command to be launched before the sequence.
        tail : list of `str`
            list of command to be launched after the sequence.
        doTest : `bool`
           image/exposure type will be labelled as test, default=dark.
        """
        return cls()


class Arcs:
    """iic expose arc [hgar=FF.F] [hgcd=FF.F] [argon=FF.F] [neon=FF.F] [krypton=FF.F] [xenon=FF.F] [@doShutterTiming]
    [switchOn=???] [switchOff=???] [cam=???] [arm=???] [sm=???] [duplicate=N] [name=\"SSS\"] [comments=\"SSS\"]
    [head=???] [tail=???] [@doTest]"""

    def __init__(self):
        """
        """
        pass

    @classmethod
    def build(cls, hgar=0, hgcd=0, argon=0, neon=0, krypton=0, xenon=0, doShutterTiming=False, switchOn=None,
              switchOff=None, cam=None, arm=None, sm=None, duplicate=1, name="", comments="", head=None, tail=None,
              doTest=False):
        """
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
        switchOn : list of str`
            lamp list to turn on before the exposure (dcb only).
        switchOff : list of str`
            lamp list to turn off after the exposure (dcb only).
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
           image/exposure type will be labelled as test, default=arc
        """
        return cls()


class Flats:
    """iic expose flat exptime=??? [noLampCtl] [switchOff] [cam=???] [arm=???] [sm=???] [duplicate=N] [name=\"SSS\"]
    [comments=\"SSS\"] [head=???] [tail=???] [@doTest]"""

    def __init__(self):
        """
        """
        pass

    @classmethod
    def build(cls, exptime, noLampCtl=False, switchOff=False, cam=None, arm=None, sm=None, duplicate=1, name="",
              comments="", head=None, tail=None, doTest=False):
        """
        Take a set of flat exposure.
        Sequence is referenced in opdb as iic_sequence.seqtype=flats.

        Parameters
        ---------
        exptime : `float`
            exposure time.
        noLampCtl : `bool`
            ignore continuum lamp control.(dcb only).
        switchOff : `bool`
            switch continuum lamp at the end (dcb only).
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
           image/exposure type will be labelled as test, default=flat
        """
        return cls()


class StartExposure:
    """iic sps @startExposures exptime=??? [cam=???] [arm=???] [sm=???] [name=\"SSS\"] [comments=\"SSS\"] [@doBias]
    [@doTest]"""

    def __init__(self):
        """
        """
        pass

    @classmethod
    def build(cls, exptime, cam=None, arm=None, sm=None, name="", comments="", doBias=False, doTest=False):
        """
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
        return cls()


class AbortExposure:
    """iic sps @abortExposure [id=N]"""

    def __init__(self):
        """
        """
        pass

    @classmethod
    def build(cls, id=None):
        """
        Abort running sequence, abort any on-going sps exposure.

        Parameters
        ---------
        id : `int`
            sequenceId to abort.
        """
        return cls()


class FinishExposure:
    """iic sps @finishExposure [id=N] [@noSunssBias]"""

    def __init__(self):
        """
        """
        pass

    @classmethod
    def build(cls, id=None, noSunssBias=False):
        """
        Finish running sequence, abort any on-going sps exposure.
        """
        return cls()
