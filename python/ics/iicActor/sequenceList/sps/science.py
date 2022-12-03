import iicActor.utils.translate as translate
from ics.iicActor.sps.sequence import SpsSequence


class ScienceObject(SpsSequence):
    """ Biases sequence """
    seqtype = 'scienceObject'
    doScienceCheck = True

    def __init__(self, cams, exptime, duplicate, windowKeys, **seqKeys):
        SpsSequence.__init__(self, cams, isWindowed=bool(windowKeys), **seqKeys)

        self.expose('object', exptime, cams, duplicate=duplicate, windowKeys=windowKeys)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        seqKeys = translate.seqKeys(cmdKeys)
        identKeys = translate.identKeys(cmdKeys)
        exptime, duplicate = translate.spsExposureKeys(cmdKeys)
        windowKeys = translate.windowKeys(cmdKeys)

        cams = iicActor.engine.resourceManager.spsConfig.identify(**identKeys)

        return cls(cams, exptime, duplicate, windowKeys, **seqKeys)


class ScienceObjectLoop(ScienceObject):
    """ Biases sequence """

    def __init__(self, cams, exptime, duplicate, windowKeys, **seqKeys):
        ScienceObject.__init__(self, cams, exptime, 1, windowKeys, **seqKeys)

    def setStatus(self, statusStr, *args, **kwargs):
        """Declare sequence as complete, that is the nominal end for a sequence."""
        # Loop until someone finish this sequence.
        if self.status.statusStr == 'active' and statusStr == 'finish':
            # append a copy of the first command.
            self.append(self[0].actor, self[0].cmdStr, timeLim=self[0].timeLim)
            return

        ScienceObject.setStatus(self, statusStr, *args, **kwargs)
