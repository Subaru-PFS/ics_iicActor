from ics.iicActor.utils.sequencing import Sequence


class SpsSequence(Sequence):
    def _appendTimedLampExposure(self, exptype, kwargs, cams=None, duplicate=1):
        exptime = 0.0
        lamps = []
        for lamp in 'halogen', 'hgar', 'argon', 'neon', 'krypton':
            if lamp in kwargs.keys():
                exptime = max(exptime, float(kwargs[lamp]))
                lamps.append(f"{lamp}={float(kwargs[lamp]):0.2f}")
        dcbCmdStr = f'sources prepare {" ".join(lamps)}'
        for i in range(duplicate):
            self.add(actor='dcb', cmdStr=dcbCmdStr)
            self.expose(exptype=exptype, exptime=exptime, cams=cams, doLamps=True)

    def appendTimedArc(self, lamps, cams=None, duplicate=1):
        """Append a complete arc exposure sequence, including lamp control. """

        self._appendTimedLampExposure('arc', lamps, cams=cams, duplicate=duplicate)

    def appendTimedFlat(self, lamps, cams=None, duplicate=1):
        """Append a complete flat exposure sequence, including lamp control. """

        self._appendTimedLampExposure('flat', lamps, cams=cams, duplicate=duplicate)


class Arc(SpsSequence):
    """ Arcs sequence """

    def __init__(self, duplicate, cams, timedLamps, **kwargs):
        SpsSequence.__init__(self, 'arcs', **kwargs)
        self.appendTimedArc(timedLamps, cams=cams, duplicate=duplicate)


class Flat(SpsSequence):
    """ Flat / fiberTrace sequence """

    def __init__(self, duplicate, cams, timedLamps, **kwargs):
        SpsSequence.__init__(self, 'flats', **kwargs)
        self.appendTimedFlat(timedLamps, cams=cams, duplicate=duplicate)


class HexapodStability(SpsSequence):
    """ hexapod stability sequence """

    def __init__(self, position, duplicate, cams, timedLamps, **kwargs):
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
        self.appendTimedArc(timedLamps, cams='{cams}', duplicate=duplicate)
        for pos in positions:
            # Move y once separately
            self.add('sps', 'slit dither', y=round(pos, 5), abs=True, cams=cams)
            for pos in positions:
                self.add('sps', f'slit dither', x=round(pos, 5), abs=True, cams=cams)
                self.appendTimedArc(timedLamps, cams='{cams}', duplicate=duplicate)
        self.add('sps', 'slit dither', x=0.0, y=0.0, abs=True, cams=cams)
        self.appendTimedArc(timedLamps, cams='{cams}', duplicate=duplicate)


class DitheredFlats(SpsSequence):
    """ TimedDitheredFlats / masterFlat sequence """

    def __init__(self, positions, duplicate, cams, timedLamps, **kwargs):
        SpsSequence.__init__(self, 'ditheredFlats', **kwargs)

        self.add(actor='sps', cmdStr='slit dither', x=0, pixels=True, abs=True, cams=cams)
        self.appendTimedFlat(timedLamps, cams='{cams}', duplicate=duplicate)

        for position in positions:
            self.add(actor='sps', cmdStr='slit dither', x=position, pixels=True, abs=True, cams=cams)
            self.appendTimedFlat(timedLamps, cams='{cams}', duplicate=duplicate)

        self.add(actor='sps', cmdStr='slit dither', x=0, pixels=True, abs=True, cams=cams)
        self.appendTimedFlat(timedLamps, cams='{cams}', duplicate=duplicate)

        self.tail.add(actor='sps', cmdStr='slit dither', x=0, y=0, pixels=True, abs=True, cams=cams)


class DitheredArcs(SpsSequence):
    """ Timed Dithered Arcs sequence """

    def __init__(self, pixels, doMinus, duplicate, cams, timedLamps, **kwargs):
        Sequence.__init__(self, 'ditheredArcs', **kwargs)

        end = int(1 / pixels)
        start = -end + 1 if doMinus else 0
        for x in range(start, end):
            for y in range(start, end):
                self.add(actor='sps', cmdStr='slit dither',
                         x=x * pixels, y=y * pixels, pixels=True, abs=True, cams=cams)
                self.appendTimedArc(timedLamps, cams='{cams}', duplicate=duplicate)

        self.tail.add(actor='sps', cmdStr='slit dither', x=0, y=0, pixels=True, abs=True, cams=cams)


class DetThroughFocus(SpsSequence):
    """ Detector through focus sequence """

    def __init__(self, positions, duplicate, cams, timedLamps, **kwargs):
        Sequence.__init__(self, 'detThroughFocus', **kwargs)

        for motorA, motorB, motorC in positions:
            self.add(actor='sps', cmdStr='ccdMotors move',
                     a=motorA, b=motorB, c=motorC, microns=True, abs=True, cams=cams)
            self.appendTimedArc(timedLamps, cams='{cams}', duplicate=duplicate)
