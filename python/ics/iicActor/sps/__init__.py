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

    def __init__(self, exptime, switchOn, attenuator, force, switchOff, duplicate, cams, **kwargs):
        Sequence.__init__(self, 'arcs', **kwargs)

        if switchOn is not None or attenuator is not None:
            self.head.add(actor='dcb', cmdStr='arc', on=switchOn, attenuator=attenuator, force=force, timeLim=300)

        if switchOff is not None:
            self.tail.insert(actor='dcb', cmdStr='arc', off=switchOff)

        self.expose(exptype='arc', exptime=exptime, cams=cams, duplicate=duplicate)


class Flat(Sequence):
    """ Flat / fiberTrace sequence """

    def __init__(self, exptime, switchOn, attenuator, force, switchOff, duplicate, cams, **kwargs):
        Sequence.__init__(self, 'flats', **kwargs)

        self.head.add(actor='dcb', cmdStr='arc', on='halogen', attenuator=attenuator, force=force, timeLim=300)

        if switchOff:
            self.tail.insert(actor='dcb', cmdStr='arc', off='halogen')

        self.expose(exptype='flat', exptime=exptime, cams=cams, duplicate=duplicate)


class SlitThroughFocus(Sequence):
    """ Slit through focus sequence """

    def __init__(self, exptime, positions, switchOn, attenuator, force, switchOff, duplicate, cams, **kwargs):
        Sequence.__init__(self, 'slitThroughFocus', **kwargs)

        if switchOn is not None:
            self.head.add(actor='dcb', cmdStr='arc', on=switchOn, attenuator=attenuator, force=force, timeLim=300)

        if switchOff is not None:
            self.tail.insert(actor='dcb', cmdStr='arc', off=switchOff)

        for position in positions:
            self.add(actor='sps', cmdStr='slit', focus=position, abs=True, cams=cams)
            self.expose(exptype='arc', exptime=exptime, cams='{cams}', duplicate=duplicate)

        self.add(actor='sps', cmdStr='slit', focus=0, abs=True, cams=cams)


class DetThroughFocus(Sequence):
    """ Detector through focus sequence """

    def __init__(self, exptime, positions, switchOn, attenuator, force, switchOff, duplicate, cams, **kwargs):
        Sequence.__init__(self, 'detThroughFocus', **kwargs)

        if switchOn is not None or attenuator is not None:
            self.head.add(actor='dcb', cmdStr='arc', on=switchOn, attenuator=attenuator, force=force, timeLim=300)

        if switchOff is not None:
            self.tail.insert(actor='dcb', cmdStr='arc', off=switchOff)

        for motorA, motorB, motorC in positions:
            self.add(actor='sps', cmdStr='ccdMotors move',
                     a=motorA, b=motorB, c=motorC, microns=True, abs=True, cams=cams)
            self.expose(exptype='arc', exptime=exptime, cams='{cams}', duplicate=duplicate)


class DitheredFlats(Sequence):
    """ Dithered Flats sequence """

    def __init__(self, exptime, positions, switchOn, attenuator, force, switchOff, duplicate, cams, **kwargs):
        Sequence.__init__(self, 'ditheredFlats', **kwargs)

        self.head.add(actor='dcb', cmdStr='arc', on='halogen', attenuator=attenuator, force=force, timeLim=300)

        if switchOff:
            self.tail.insert(actor='dcb', cmdStr='arc', off='halogen')

        self.add(actor='sps', cmdStr='slit dither', x=0, pixels=True, abs=True, cams=cams)
        self.expose(exptype='flat', exptime=exptime, cams='{cams}', duplicate=duplicate)

        for position in positions:
            self.add(actor='sps', cmdStr='slit dither', x=position, pixels=True, abs=True, cams=cams)
            self.expose(exptype='flat', exptime=exptime, cams='{cams}', duplicate=duplicate)

        self.add(actor='sps', cmdStr='slit dither', x=0, pixels=True, abs=True, cams=cams)
        self.expose(exptype='flat', exptime=exptime, cams='{cams}', duplicate=duplicate)


class DitheredArcs(Sequence):
    """ Dithered Arcs sequence """

    def __init__(self, exptime, pixels, switchOn, attenuator, force, switchOff, duplicate, cams, **kwargs):
        Sequence.__init__(self, 'ditheredArcs', **kwargs)

        if switchOn is not None or attenuator is not None:
            self.head.add(actor='dcb', cmdStr='arc', on=switchOn, attenuator=attenuator, force=force, timeLim=300)

        if switchOff is not None:
            self.tail.insert(actor='dcb', cmdStr='arc', off=switchOff)

        for x in range(int(1 / pixels)):
            for y in range(int(1 / pixels)):
                self.add(actor='sps', cmdStr='slit dither', x=x * pixels, y=y * pixels, pixels=True, abs=True, cams=cams)
                self.expose(exptype='arc', exptime=exptime, cams='{cams}', duplicate=duplicate)

        self.add(actor='sps', cmdStr='slit dither', x=0, y=0, pixels=True, abs=True, cams=cams)


class Defocus(Sequence):
    """ Defocus sequence """

    def __init__(self, exptime, positions, switchOn, attenuator, force, switchOff, duplicate, cams, **kwargs):
        Sequence.__init__(self, 'defocusedArcs', **kwargs)

        if switchOn is not None:
            self.head.add(actor='dcb', cmdStr='arc', on=switchOn, attenuator=attenuator, force=force, timeLim=300)

        if switchOff is not None:
            self.tail.insert(actor='dcb', cmdStr='arc', off=switchOff)

        for position in positions:
            cexptime, catten = defocused_exposure_times_single_position(exp_time_0=exptime,
                                                                        att_value_0=attenuator,
                                                                        defocused_value=position)
            if attenuator is not None:
                self.add(actor='dcb', cmdStr='arc', attenuator=catten, timeLim=300)

            self.add(actor='sps', cmdStr='slit', focus=position, abs=True, cams=cams)
            self.expose(exptype='arc', exptime=cexptime, cams='{cams}', duplicate=duplicate)

        self.add(actor='sps', cmdStr='slit', focus=0, abs=True, cams=cams)
