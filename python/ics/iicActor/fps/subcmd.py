from ics.iicActor.utils.subcmd import VisitedCmd


class FpsCmd(VisitedCmd):
    """ Placeholder to handle dcb command specificities"""

    def __init__(self, cmdStr, timeLim=120, **kwargs):
        VisitedCmd.__init__(self, 'fps', cmdStr, timeLim=timeLim, **kwargs)
