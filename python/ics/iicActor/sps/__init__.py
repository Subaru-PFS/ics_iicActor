from ics.iicActor.utils.sequencing import Sequence
from pfs.utils.ncaplar import defocused_exposure_times_single_position


class Object(Sequence):
    """ Simple exposure sequence """

    def __init__(self, exptime, duplicate, cams, **kwargs):
        Sequence.__init__(self, 'object', **kwargs)
        self.expose(exptype='object', exptime=exptime, cams=cams, duplicate=duplicate)


class Bias(Sequence):
    """ Biases sequence """

    def __init__(self, duplicate, cams, **kwargs):
        Sequence.__init__(self, 'biases', **kwargs)
        self.expose(exptype='bias', cams=cams, duplicate=duplicate)


class Dark(Sequence):
    """ Darks sequence """

    def __init__(self, exptime, duplicate, cams, **kwargs):
        Sequence.__init__(self, 'darks', **kwargs)
        self.expose(exptype='dark', exptime=exptime, cams=cams, duplicate=duplicate)


class Arc(Sequence):
    """ Arcs sequence """

    def __init__(self, exptime, duplicate, cams, dcbOn, dcbOff, iisOn, iisOff, **kwargs):
        Sequence.__init__(self, 'arcs', **kwargs)

        if any(dcbOn.values()):
            self.head.add(actor='dcb', cmdStr='arc', **dcbOn)

        if any(iisOn.values()):
            self.head.add(actor='sps', cmdStr='iis', cams=cams, **iisOn)

        if any(dcbOff.values()):
            self.tail.add(index=0, actor='dcb', cmdStr='arc', **dcbOff)

        if any(iisOff.values()):
            self.tail.add(index=0, actor='sps', cmdStr='iis', cams=cams, **iisOff)

        cams = '{cams}' if any(iisOn.values()) else cams
        self.expose(exptype='arc', exptime=exptime, cams=cams, duplicate=duplicate)


class Flat(Sequence):
    """ Flat / fiberTrace sequence """

    def __init__(self, exptime, duplicate, cams, dcbOn, dcbOff, **kwargs):
        Sequence.__init__(self, 'flats', **kwargs)

        if any(dcbOn.values()):
            self.head.add(actor='dcb', cmdStr='arc', **dcbOn)

        if any(dcbOff.values()):
            self.tail.add(index=0, actor='dcb', cmdStr='arc', **dcbOff)
        self.expose(exptype='flat', exptime=exptime, cams=cams, duplicate=duplicate)

class SpsSequence(Sequence):
    def _appendTimedLampExposure(self, exptype, kwargs, cams=None, duplicate=1):
        exptime = 0.0
        lamps = []
        for lamp in 'halogen','hgar','argon','neon','krypton':
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

class TimedArc(SpsSequence):
    """ Arcs sequence """

    def __init__(self, duplicate, cams, **kwargs):
        SpsSequence.__init__(self, 'arcs',
                             head=kwargs.get('head', None),
                             tail=kwargs.get('tail', None))

        self.appendTimedArc(kwargs, cams=cams, duplicate=duplicate)

class TimedFlat(SpsSequence):
    """ Flat / fiberTrace sequence """

    def __init__(self, exptime, duplicate, cams, **kwargs):
        SpsSequence.__init__(self, 'flats',
                             head=kwargs.get('head', None),
                             tail=kwargs.get('tail', None))
        self.appendTimedFlat(kwargs, cams=cams, duplicate=duplicate)

class SlitThroughFocus(Sequence):
    """ Slit through focus sequence """

    def __init__(self, exptime, positions, duplicate, cams, dcbOn, dcbOff, **kwargs):
        Sequence.__init__(self, 'slitThroughFocus', **kwargs)

        if any(dcbOn.values()):
            self.head.add(actor='dcb', cmdStr='arc', **dcbOn)

        if any(dcbOff.values()):
            self.tail.add(index=0, actor='dcb', cmdStr='arc', **dcbOff)

        for position in positions:
            self.add(actor='sps', cmdStr='slit', focus=position, abs=True, cams=cams)
            self.expose(exptype='arc', exptime=exptime, cams='{cams}', duplicate=duplicate)

        self.tail.add(actor='sps', cmdStr='slit', focus=0, abs=True, cams=cams)


class DetThroughFocus(Sequence):
    """ Detector through focus sequence """

    def __init__(self, exptime, positions, duplicate, cams, dcbOn, dcbOff, **kwargs):
        Sequence.__init__(self, 'detThroughFocus', **kwargs)

        if any(dcbOn.values()):
            self.head.add(actor='dcb', cmdStr='arc', **dcbOn)

        if any(dcbOff.values()):
            self.tail.add(index=0, actor='dcb', cmdStr='arc', **dcbOff)

        for motorA, motorB, motorC in positions:
            self.add(actor='sps', cmdStr='ccdMotors move',
                     a=motorA, b=motorB, c=motorC, microns=True, abs=True, cams=cams)
            self.expose(exptype='arc', exptime=exptime, cams='{cams}', duplicate=duplicate)

class HexapodStability(SpsSequence):
    """ hexapod stability sequence """

    def __init__(self, positions=None, duplicate=1, cams=None, lamps=None):
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
        SpsSequence.__init__(self, 'hexapodStability')

        if positions is None:
            positions = np.arange(-0.05,0.055,0.01)[::-1]
        if lamps is None:
            lamps = dict(argon=60)

        sm = 1
        cams = None # [f'r{sm}']

        self.add('sps', 'slit focus=0.0 abs')
        self.add('sps', 'slit dither x=0.0 y=0.0 abs')
        self.appendTimedArc(lamps, cams, duplicate=duplicate)
        for pos in positions:
            # Move y once separately
            self.add('sps', f'slit dither y={pos:1.3f} abs')
            for pos in positions:
                self.add('sps', f'slit dither x={pos:1.3f} abs')
                self.appendTimedArc(lamps, cams, duplicate=duplicate)
        self.add('sps', f'slit dither x=0.0 y=0.0 abs')
        self.appendTimedArc(lamps, cams, duplicate=duplicate)

class DitheredFlats(Sequence):
    """ Dithered Flats sequence """

    def __init__(self, exptime, positions, duplicate, cams, dcbOn, dcbOff, **kwargs):
        Sequence.__init__(self, 'ditheredFlats', **kwargs)

        if any(dcbOn.values()):
            self.head.add(actor='dcb', cmdStr='arc', **dcbOn)

        if any(dcbOff.values()):
            self.tail.add(index=0, actor='dcb', cmdStr='arc', **dcbOff)

        self.add(actor='sps', cmdStr='slit dither', x=0, pixels=True, abs=True, cams=cams)
        self.expose(exptype='flat', exptime=exptime, cams='{cams}', duplicate=duplicate)

        for position in positions:
            self.add(actor='sps', cmdStr='slit dither', x=position, pixels=True, abs=True, cams=cams)
            self.expose(exptype='flat', exptime=exptime, cams='{cams}', duplicate=duplicate)

        self.add(actor='sps', cmdStr='slit dither', x=0, pixels=True, abs=True, cams=cams)
        self.expose(exptype='flat', exptime=exptime, cams='{cams}', duplicate=duplicate)

        self.tail.add(actor='sps', cmdStr='slit dither', x=0, y=0, pixels=True, abs=True, cams=cams)

class DitheredArcs(Sequence):
    """ Dithered Arcs sequence """

    def __init__(self, exptime, pixels, doMinus, duplicate, cams, dcbOn, dcbOff, **kwargs):
        Sequence.__init__(self, 'ditheredArcs', **kwargs)

        if any(dcbOn.values()):
            self.head.add(actor='dcb', cmdStr='arc', **dcbOn)

        if any(dcbOff.values()):
            self.tail.add(index=0, actor='dcb', cmdStr='arc', **dcbOff)

        end = int(1 / pixels)
        start = -end + 1 if doMinus else 0
        for x in range(start, end):
            for y in range(start, end):
                self.add(actor='sps', cmdStr='slit dither',
                         x=x * pixels, y=y * pixels, pixels=True, abs=True, cams=cams)
                self.expose(exptype='arc', exptime=exptime, cams='{cams}', duplicate=duplicate)

        self.tail.add(actor='sps', cmdStr='slit dither', x=0, y=0, pixels=True, abs=True, cams=cams)


class Defocus(Sequence):
    """ Defocus sequence """

    def __init__(self, exp_time_0, positions, duplicate, cams, dcbOn, dcbOff, **kwargs):
        Sequence.__init__(self, 'defocusedArcs', **kwargs)
        att_value_0 = dcbOn['attenuator']

        if any(dcbOn.values()):
            self.head.add(actor='dcb', cmdStr='arc', **dcbOn)

        if any(dcbOff.values()):
            self.tail.add(index=0, actor='dcb', cmdStr='arc', **dcbOff)

        for position in positions:
            exptime, attenuator = defocused_exposure_times_single_position(exp_time_0=exp_time_0[0],
                                                                           att_value_0=att_value_0,
                                                                           defocused_value=position)
            if att_value_0 is not None:
                self.add(actor='dcb', cmdStr='arc', attenuator=attenuator, timeLim=300)

            self.add(actor='sps', cmdStr='slit', focus=position, abs=True, cams=cams)
            self.expose(exptype='arc', exptime=exptime, cams='{cams}', duplicate=duplicate)

        self.tail.add(actor='sps', cmdStr='slit', focus=0, abs=True, cams=cams)


class Custom(Sequence):
    """ Custom sequence """

    def __init__(self, duplicate, cams, **kwargs):
        Sequence.__init__(self, 'custom', **kwargs)
