from ics.iicActor.fps.sequence import FpsSequence


class MovePhiToAngle(FpsSequence):
    """ Flat/fiberTrace from Dome illumination. """
    seqtype = 'movePhiToAngle'
    timeLim = 900
    dependencies = ['mcs']

    def __init__(self, angle, iteration, doTest=False, **kwargs):
        FpsSequence.__init__(self, **kwargs)
        self.fpsCommand(angle=angle, iteration=iteration)
