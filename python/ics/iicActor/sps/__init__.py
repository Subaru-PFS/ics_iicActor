from ics.iicActor.utils.sequencing import Sequence


class Object(Sequence):
    """ Simple exposure sequence """

    def __init__(self, exptime, duplicate, cams, name, comments, head, tail):
        Sequence.__init__(self, 'object', name=name, comments=comments, head=head, tail=tail)
        self.add(actor='sps',
                 cmdStr=f'expose object exptime={exptime} visit={{visit}} {cams}',
                 timeLim=120 + exptime,
                 duplicate=duplicate)


class Bias(Sequence):
    """ Biases sequence """

    def __init__(self, duplicate, cams, name, comments, head, tail):
        Sequence.__init__(self, 'biases', name=name, comments=comments, head=head, tail=tail)
        self.add(actor='sps',
                 cmdStr=f'expose bias visit={{visit}} {cams}',
                 timeLim=120,
                 duplicate=duplicate)


class Dark(Sequence):
    """ Darks sequence """

    def __init__(self, exptime, duplicate, cams, name, comments, head, tail):
        Sequence.__init__(self, 'darks', name=name, comments=comments, head=head, tail=tail)
        self.add(actor='sps',
                 cmdStr=f'expose dark exptime={exptime} visit={{visit}} {cams}',
                 timeLim=120 + exptime,
                 duplicate=duplicate)


class Arc(Sequence):
    """ Arcs sequence """

    def __init__(self, exptime, onArgs, offArgs, duplicate, cams, name, comments, head, tail):
        Sequence.__init__(self, 'arcs', name=name, comments=comments, head=head, tail=tail)

        if onArgs:
            self.head.add(actor='dcb',
                          cmdStr=f'arc {" ".join(onArgs)}',
                          timeLim=300)

        if offArgs:
            self.tail.insert(actor='dcb',
                             cmdStr=f'arc {" ".join(offArgs)}')

        self.add(actor='sps',
                 cmdStr=f'expose arc exptime={exptime} visit={{visit}} {cams}',
                 timeLim=120 + exptime,
                 duplicate=duplicate)


class Flat(Sequence):
    """ Flat sequence """

    def __init__(self, exptime, attenArgs, switchOff, duplicate, cams, name, comments, head, tail):
        Sequence.__init__(self, 'flats', name=name, comments=comments, head=head, tail=tail)

        self.head.add(actor='dcb',
                      cmdStr=f'arc on=halogen {" ".join(attenArgs)}',
                      timeLim=300)

        if switchOff:
            self.tail.insert(actor='dcb',
                             cmdStr='arc off=halogen')

        self.add(actor='sps',
                 cmdStr=f'expose flat exptime={exptime} visit={{visit}} {cams}',
                 timeLim=120 + exptime,
                 duplicate=duplicate)


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

