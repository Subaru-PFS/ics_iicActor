from ics.iicActor.utils.sequencing import Sequence


class Object(Sequence):
    """ Simple exposure sequence """

    def __init__(self, exptime, duplicate, cams, name, comments, head, tail):
        Sequence.__init__(self, 'object', name=name, comments=comments, head=head, tail=tail)
        self.addSubCmd(actor='sps',
                       cmdStr=f'expose object exptime={exptime} visit={{visit}} {cams}',
                       timeLim=120 + exptime,
                       duplicate=duplicate)


class Bias(Sequence):
    """ Biases sequence """

    def __init__(self, duplicate, cams, name, comments, head, tail):
        Sequence.__init__(self, 'biases', name=name, comments=comments, head=head, tail=tail)
        self.addSubCmd(actor='sps',
                       cmdStr=f'expose bias visit={{visit}} {cams}',
                       timeLim=120,
                       duplicate=duplicate)


class Dark(Sequence):
    """ Darks sequence """

    def __init__(self, exptime, duplicate, cams, name, comments, head, tail):
        Sequence.__init__(self, 'darks', name=name, comments=comments, head=head, tail=tail)
        self.addSubCmd(actor='sps',
                       cmdStr=f'expose dark exptime={exptime} visit={{visit}} {cams}',
                       timeLim=120 + exptime,
                       duplicate=duplicate)


class Arc(Sequence):
    """ Arcs sequence """

    def __init__(self, exptime, switchOn, switchOff, attenuator, force, duplicate, cams, name, comments, head, tail):
        Sequence.__init__(self, 'arcs', name=name, comments=comments, head=head, tail=tail)

        if switchOn is not None:
            attenuator = f'attenuator={attenuator}' if attenuator is not None else ''
            force = 'force' if force else ''
            self.head.addSubCmd(actor='dcb',
                                cmdStr="arc on=%s %s %s" % (','.join(switchOn), attenuator, force),
                                timeLim=300)

        if switchOff is not None:
            self.tail.insert(actor='dcb',
                             cmdStr="arc off=%s" % ','.join(switchOff))

        self.addSubCmd(actor='sps',
                       cmdStr=f'expose arc exptime={exptime} visit={{visit}} {cams}',
                       timeLim=120 + exptime,
                       duplicate=duplicate)
