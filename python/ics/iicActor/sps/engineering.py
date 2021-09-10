from ics.iicActor.utils.sequencing import Sequence


class SpsEngSequence(Sequence):
    def __init__(self):
        Sequence.__init__(self, name='spsEngSequence', comments="")

    def insertSequence(self):
        """ Do nothing yet... """
        pass

    def insertVisitSet(self, visit):
        """ Do nothing yet """

    def finalize(self, cmd):
        """  Do nothing yet """
        self.isDone = True
        cmd.inform(self.genKeys())


class RdaMove(SpsEngSequence):
    """ Rda move sequence """
    seqtype = 'rdaMove'

    def __init__(self, specNames):
        SpsEngSequence.__init__(self)
        self.add(actor='sps', cmdStr=f'rda moveTo {self.targetPosition}', sm=','.join(specNames), timeLim=180)


class RdaLow(RdaMove):
    targetPosition = 'low'


class RdaMed(RdaMove):
    targetPosition = 'med'
