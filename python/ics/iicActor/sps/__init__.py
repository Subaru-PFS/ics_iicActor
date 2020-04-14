from ics.iicActor.utils.sequencing import Sequence


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
    """ Flat sequence """

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
            self.add(actor='sps', cmdStr='slit', focus=position, cams=cams, timeLim=30)
            self.expose(exptype='arc', exptime=exptime, duplicate=duplicate, cams='{cams}')


class DetThroughFocus(Sequence):
    """ Detector through focus sequence """

    def __init__(self, exptime, positions, switchOn, attenuator, force, switchOff, duplicate, cams, **kwargs):
        Sequence.__init__(self, 'detThroughFocus', **kwargs)

        if switchOn is not None or attenuator is not None:
            self.head.add(actor='dcb', cmdStr='arc', on=switchOn, attenuator=attenuator, force=force, timeLim=300)

        if switchOff is not None:
            self.tail.insert(actor='dcb', cmdStr='arc', off=switchOff)

        for motorA, motorB, motorC in positions:
            self.add(actor='sps', cmdStr='ccdMotors move', a=motorA, b=motorB, c=motorC, cams=cams, timeLim=30)
            self.expose(exptype='arc', exptime=exptime, duplicate=duplicate, cams='{cams}')
