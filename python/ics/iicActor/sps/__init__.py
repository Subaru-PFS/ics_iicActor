from ics.iicActor.utils.sequencing import Sequence


class Object(Sequence):
    """ Simple exposure sequence """

    def __init__(self, exptime, duplicate, cams, name, comments, head, tail):
        Sequence.__init__(self, 'object', name=name, comments=comments, head=head, tail=tail)
        self.addSubCmd(actor='sps',
                       cmdStr=f'expose object exptime={exptime} visit={{visit}} {cams}',
                       timeLim=120 + exptime,
                       duplicate=duplicate)
