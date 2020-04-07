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

    def __init__(self, exptime, switchOn, switchOff, attenuator, force, duplicate, cams, name, comments, head, tail):
        Sequence.__init__(self, 'arcs', name=name, comments=comments, head=head, tail=tail)

        if switchOn is not None:
            args = [f'on={",".join(switchOn)}']
            args += ([f'attenuator={attenuator}'] if attenuator is not None else [])
            args += (['force'] if force else [])
            self.head.add(actor='dcb',
                          cmdStr=f'arc {" ".join(args)}',
                          timeLim=300)

        if switchOff is not None:
            self.tail.insert(actor='dcb',
                             cmdStr=f'arc off={",".join(switchOff)}')

        self.add(actor='sps',
                 cmdStr=f'expose arc exptime={exptime} visit={{visit}} {cams}',
                 timeLim=120 + exptime,
                 duplicate=duplicate)


class Flat(Sequence):
    """ Flat sequence """

    def __init__(self, exptime, switchOff, attenuator, force, duplicate, cams, name, comments, head, tail):
        Sequence.__init__(self, 'flats', name=name, comments=comments, head=head, tail=tail)

        args = [f'attenuator={attenuator}'] if attenuator is not None else []
        args += (['force'] if force else [])
        self.head.add(actor='dcb',
                      cmdStr=f'arc on=halogen {" ".join(args)}',
                      timeLim=300)

        if switchOff:
            self.tail.insert(actor='dcb',
                             cmdStr='arc off=halogen')

        self.add(actor='sps',
                 cmdStr=f'expose flat exptime={exptime} visit={{visit}} {cams}',
                 timeLim=120 + exptime,
                 duplicate=duplicate)
