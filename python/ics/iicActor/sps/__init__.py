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
