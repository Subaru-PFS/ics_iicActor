from ics.iicActor.fps.subcmd import FpsCmd
from ics.iicActor.utils.sequencing import Sequence


class FpsSequence(Sequence):
    """Capture Fps sequence specificities here..."""

    def fpsCommand(self, **kwargs):
        """ Append duplicate * sps expose to sequence """
        self.append(FpsCmd(self.seqtype, **kwargs))