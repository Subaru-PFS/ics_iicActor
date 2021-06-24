from ics.iicActor.fps.subcmd import FpsCmd
from ics.iicActor.utils.sequencing import Sequence


class FpsSequence(Sequence):
    """Capture SpS sequence specificities here..."""

    def __init__(self, *args, **kwargs):
        Sequence.__init__(self, *args, **kwargs)

    def fpsCommand(self, **kwargs):
        """ Append duplicate * sps expose to sequence """
        self.append(FpsCmd(self.seqtype, **kwargs))
