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
