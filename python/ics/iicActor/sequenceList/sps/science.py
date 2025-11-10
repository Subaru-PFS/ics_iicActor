import ics.iicActor.utils.translate as translate
from ics.iicActor.sps.sequence import SpsSequence
from ics.iicActor.utils.sequenceStatus import Flag


class ScienceObject(SpsSequence):
    """ Biases sequence """
    seqtype = 'scienceObject'
    doScienceCheck = True

    def __init__(self, cams, exptime, duplicate, windowKeys, mcsExposureBefore, **seqKeys):
        isWindowed = bool(windowKeys)
        SpsSequence.__init__(self, cams, isWindowed=isWindowed, **seqKeys)

        # forcing to None for windowed exposure if specified in config file.
        if isWindowed and mcsExposureBefore['skipWindowed']:
            mcsExposureBefore['enabled'] = False

        self.expose('object', exptime, cams,
                    duplicate=duplicate, windowKeys=windowKeys, mcsExposureBefore=mcsExposureBefore)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        cams = SpsSequence.keysToCam(iicActor, cmdKeys)
        seqKeys = translate.seqKeys(cmdKeys)
        exptime, duplicate = translate.spsExposureKeys(cmdKeys)
        windowKeys = translate.windowKeys(cmdKeys)

        config = iicActor.actorConfig['scienceExposure']
        mcsExposureBefore = config.get('mcsExposureBefore')

        return cls(cams, exptime, duplicate, windowKeys, mcsExposureBefore, **seqKeys)


class ScienceObjectLoop(ScienceObject):
    """ Biases sequence """

    def __init__(self, cams, exptime, duplicate, windowKeys, mcsExposureBefore, **seqKeys):
        mcsExposureBefore['enabled'] = False
        ScienceObject.__init__(self, cams, exptime, 1, windowKeys, mcsExposureBefore, **seqKeys)

    def commandLogic(self, *args, **kwargs):
        """Declare sequence as complete, that is the nominal end for a sequence."""
        ScienceObject.commandLogic(self, *args, **kwargs)

        # Loop until someone finish this sequence.
        if self.status.flag == Flag.FINISHED:
            # append a copy of the first command.
            self.append(self[0].actor, self[0].cmdStr, timeLim=self[0].timeLim)
            # setting status back to ready.
            self.status.amend()
            # execute command again.
            self.commandLogic(*args, **kwargs)
