from ics.iicActor.utils.sequencing import Sequence
from pfs.utils.ncaplar import defocused_exposure_times_single_position


class SpsSequence(Sequence):
    shutterRequired = False

    def _appendTimedLampExposure(self, exptype, kwargs, cams=None, duplicate=1, doTest=False):
        exptime = 0.0
        lamps = []
        for lamp in 'halogen', 'hgar', 'argon', 'neon', 'krypton':
            if lamp in kwargs.keys():
                exptime = max(exptime, float(kwargs[lamp]))
                lamps.append(f"{lamp}={float(kwargs[lamp]):0.2f}")
        dcbCmdStr = f'sources prepare {" ".join(lamps)}'
        for i in range(duplicate):
            self.add(actor='dcb', cmdStr=dcbCmdStr)
            self.expose(exptype=exptype, exptime=exptime, cams=cams, doLamps=True, doTest=doTest)

    def appendTimedArc(self, lamps, cams=None, duplicate=1, doTest=False):
        """Append a complete arc exposure sequence, including lamp control. """

        self._appendTimedLampExposure('arc', lamps, cams=cams, duplicate=duplicate, doTest=doTest)

    def appendTimedFlat(self, lamps, cams=None, duplicate=1, doTest=False):
        """Append a complete flat exposure sequence, including lamp control. """

        self._appendTimedLampExposure('flat', lamps, cams=cams, duplicate=duplicate, doTest=doTest)


class Arcs(SpsSequence):
    """ Arcs sequence """

    def __init__(self, duplicate, cams, timedLamps, seqtype='arcs', doTest=False, **kwargs):
        SpsSequence.__init__(self, seqtype, **kwargs)
        self.appendTimedArc(timedLamps, cams=cams, duplicate=duplicate, doTest=doTest)


class Flats(SpsSequence):
    """ Flat / fiberTrace sequence """

    def __init__(self, duplicate, cams, timedLamps, seqtype='flats', doTest=False, **kwargs):
        SpsSequence.__init__(self, seqtype, **kwargs)
        self.appendTimedFlat(timedLamps, cams=cams, duplicate=duplicate, doTest=doTest)


class HexapodStability(SpsSequence):
    """ hexapod stability sequence """

    def __init__(self, position, duplicate, cams, timedLamps, doTest=False, **kwargs):
        """Acquire a hexapod repeatability grid.

        Args
        ----
        positions : vector of `float`
          the positions for the slit dither and shift grid.
          Default=[0.05, 0.04, 0.03, 0.02, 0.01, 0, -0.01, -0.02, -0.03, -0.04, -0.05]
        duplicate : `int`
          the number of exposures to take at each position.

        Notes
        -----
        The cams/sm needs to be worked out:
          - with DCB, we can only illuminate one SM, and only the red right now.
          - with pfiLamps, all SMs will be illuminated, but probably still only red.

        """
        SpsSequence.__init__(self, 'hexapodStability', **kwargs)
        if not timedLamps:
            timedLamps = dict(argon=45)

        positions = position[::-1]

        self.add('sps', 'slit', focus=0.0, abs=True)
        self.add('sps', 'slit dither', x=0.0, y=0.0, abs=True, cams=cams)
        self.appendTimedArc(timedLamps, cams='{cams}', duplicate=duplicate, doTest=doTest)
        for pos in positions:
            # Move y once separately
            self.add('sps', 'slit dither', y=round(pos, 5), abs=True, cams=cams)
            for pos in positions:
                self.add('sps', f'slit dither', x=round(pos, 5), abs=True, cams=cams)
                self.appendTimedArc(timedLamps, cams='{cams}', duplicate=duplicate, doTest=doTest)
        self.add('sps', 'slit dither', x=0.0, y=0.0, abs=True, cams=cams)
        self.appendTimedArc(timedLamps, cams='{cams}', duplicate=duplicate, doTest=doTest)


class DitheredFlats(SpsSequence):
    """ TimedDitheredFlats / masterFlat sequence """

    def __init__(self, positions, duplicate, cams, timedLamps, doTest=False, **kwargs):
        SpsSequence.__init__(self, 'ditheredFlats', **kwargs)

        self.add(actor='sps', cmdStr='slit dither', x=0, pixels=True, abs=True, cams=cams)
        self.appendTimedFlat(timedLamps, cams='{cams}', duplicate=duplicate, doTest=doTest)

        for position in positions:
            self.add(actor='sps', cmdStr='slit dither', x=position, pixels=True, abs=True, cams=cams)
            self.appendTimedFlat(timedLamps, cams='{cams}', duplicate=duplicate, doTest=doTest)

        self.add(actor='sps', cmdStr='slit dither', x=0, pixels=True, abs=True, cams=cams)
        self.appendTimedFlat(timedLamps, cams='{cams}', duplicate=duplicate, doTest=doTest)

        self.tail.add(actor='sps', cmdStr='slit dither', x=0, y=0, pixels=True, abs=True, cams=cams)


class DitheredArcs(SpsSequence):
    """ Timed Dithered Arcs sequence """

    def __init__(self, pixels, doMinus, duplicate, cams, timedLamps, doTest=False, **kwargs):
        Sequence.__init__(self, 'ditheredArcs', **kwargs)

        end = int(1 / pixels)
        start = -end + 1 if doMinus else 0
        for x in range(start, end):
            for y in range(start, end):
                self.add(actor='sps', cmdStr='slit dither',
                         x=x * pixels, y=y * pixels, pixels=True, abs=True, cams=cams)
                self.appendTimedArc(timedLamps, cams='{cams}', duplicate=duplicate, doTest=doTest)

        self.tail.add(actor='sps', cmdStr='slit dither', x=0, y=0, pixels=True, abs=True, cams=cams)


class DetThroughFocus(SpsSequence):
    """ Detector through focus sequence """

    def __init__(self, positions, duplicate, cams, timedLamps, doTest=False, **kwargs):
        Sequence.__init__(self, 'detThroughFocus', **kwargs)

        for motorA, motorB, motorC in positions:
            self.add(actor='sps', cmdStr='ccdMotors move',
                     a=motorA, b=motorB, c=motorC, microns=True, abs=True, cams=cams)
            self.appendTimedArc(timedLamps, cams='{cams}', duplicate=duplicate, doTest=doTest)


def defocused_exposure_times_no_atten(exp_time_0, defocused_value):
    exptime, __ = defocused_exposure_times_single_position(exp_time_0=exp_time_0, att_value_0=None,
                                                           defocused_value=defocused_value)
    return exptime


class DefocusedArcs(SpsSequence):
    """ Defocus sequence """

    def __init__(self, positions, duplicate, cams, timedLamps, doTest=False, **kwargs):
        Sequence.__init__(self, 'defocusedArcs', **kwargs)
        timedLamps0 = [(k, v) for k, v in timedLamps.items()]

        for position in positions:
            calcExptime = [defocused_exposure_times_no_atten(exptime, position) for lamp, exptime in timedLamps0]
            calcTimedLamps = dict([(lamp, exptime) for (lamp, __), exptime in zip(timedLamps0, calcExptime)])
            self.add(actor='sps', cmdStr='slit', focus=position, abs=True, cams=cams)
            self.appendTimedArc(calcTimedLamps, cams='{cams}', duplicate=duplicate, doTest=doTest)
