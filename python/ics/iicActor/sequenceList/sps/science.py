import ics.iicActor.utils.translate as translate
from ics.iicActor.sps.sequence import SpsSequence
from ics.iicActor.utils.sequenceStatus import Flag


class ScienceObject(SpsSequence):
    """ Biases sequence """
    seqtype = 'scienceObject'
    doScienceCheck = True

    def __init__(self, cams, exptime, duplicate, windowKeys, mcsExposureBefore, iisKeys=None, **seqKeys):
        isWindowed = bool(windowKeys)
        doIIS = bool(iisKeys)
        SpsSequence.__init__(self, cams, isWindowed=isWindowed, doIIS=doIIS, **seqKeys)

        self.expose('object', exptime, cams,
                    duplicate=duplicate, windowKeys=windowKeys, mcsExposureBefore=mcsExposureBefore,
                    iisKeys=iisKeys)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        cams = SpsSequence.keysToCam(iicActor, cmdKeys)
        seqKeys = translate.seqKeys(cmdKeys)
        exptime, duplicate = translate.spsExposureKeys(cmdKeys)
        windowKeys = translate.windowKeys(cmdKeys)
        isWindowed = bool(windowKeys)
        iisKeys = translate.iisKeys(cmdKeys)

        # the lamp is fired inside the shutter window, so it has to fit in the shortest one.
        __, iisOnTime, __ = translate.timedLampsCmdStr(iisKeys)
        if iisOnTime > min(exptime):
            raise ValueError(f'iis on-time ({iisOnTime:g}s) longer than exptime ({min(exptime):g}s)')

        config = iicActor.actorConfig['scienceExposure']
        mcsExposureBefore = config.get('mcsExposureBefore').copy()

        # Forcing to False for windowed exposure if specified in config file or directly specified in command.
        if (isWindowed and mcsExposureBefore['skipWindowed']) or 'skipMcsExposure' in cmdKeys:
            mcsExposureBefore['enabled'] = False

        return cls(cams, exptime, duplicate, windowKeys, mcsExposureBefore, iisKeys=iisKeys, **seqKeys)


class ScienceObjectLoop(ScienceObject):
    """ Biases sequence """

    def __init__(self, cams, exptime, duplicate, windowKeys, mcsExposureBefore, **seqKeys):
        ScienceObject.__init__(self, cams, exptime, 1, windowKeys, mcsExposureBefore, **seqKeys)
        # each round repeats the first exposure, checked like the first one was.
        firstExptime = exptime[0] if isinstance(exptime, list) else exptime
        self.loopExposure = dict(exptime=firstExptime, cams=cams, windowKeys=windowKeys,
                                 mcsExposureBefore=mcsExposureBefore)

    def commandLogic(self, *args, **kwargs):
        """Declare sequence as complete, that is the nominal end for a sequence."""
        ScienceObject.commandLogic(self, *args, **kwargs)

        # Loop until someone finish this sequence.
        if self.status.flag == Flag.FINISHED:
            # append the next exposure, with its checkReady, and number what was appended.
            first = len(self.cmdList)
            self.expose('object', **self.loopExposure)
            for id, subCmd in enumerate(self.cmdList[first:], start=first):
                subCmd.init(id, cmd=self.getCmd())
            # setting status back to ready.
            self.status.amend()
            # execute command again.
            self.commandLogic(*args, **kwargs)
