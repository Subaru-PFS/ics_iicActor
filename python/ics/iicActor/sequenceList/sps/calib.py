import iicActor.utils.translate as translate
from ics.iicActor.sps.sequence import SpsSequence
from ics.iicActor.sps.timedLamps import TimedLampsSequence
from iicActor.sequenceList.sps.base import Biases, Darks, Arcs, Flats


class MasterBiases(Biases):
    """ Biases sequence """
    seqtype = 'masterBiases'

    def __init__(self, cams, duplicate, **seqKeys):
        # setting minimum to 15
        duplicate = max(duplicate, 15)
        seqKeys['name'] = 'calibProduct' if not seqKeys['name'] else seqKeys['name']

        Biases.__init__(self, cams, duplicate, **seqKeys)


class MasterDarks(Darks):
    """ Biases sequence """
    seqtype = 'masterDarks'

    def __init__(self, cams, exptime, duplicate, **seqKeys):
        # setting minimum to 15
        duplicate = max(duplicate, 15)
        seqKeys['name'] = 'calibProduct' if not seqKeys['name'] else seqKeys['name']

        Darks.__init__(self, cams, exptime, duplicate, **seqKeys)


class DitheredFlats(TimedLampsSequence):
    """ Dithered Flats sequence """
    seqtype = 'ditheredFlats'

    def __init__(self, cams, lampsKeys, positions, duplicate, **seqKeys):
        SpsSequence.__init__(self, cams, **seqKeys)

        # taking a trace before starting hexapod.
        self.expose('flat', lampsKeys, cams, duplicate=duplicate)
        self.add('sps', 'slit start', cams=cams)

        # taking a trace in home to start.
        self.add('sps', 'slit home', cams=cams)
        self.expose('flat', lampsKeys, cams, duplicate=duplicate)

        for position in positions:
            self.add('sps', 'slit dither', x=position, pixels=True, abs=True, cams=cams)
            self.expose('flat', lampsKeys, cams, duplicate=duplicate)

        # taking a trace in home to end.
        self.add('sps', 'slit home', cams=cams)
        self.expose('flat', lampsKeys, cams, duplicate=duplicate)

        # taking a trace after the hexapod is turned back off.
        self.add('sps', 'slit stop', cams=cams)
        self.expose('flat', lampsKeys, cams, duplicate=duplicate)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        seqKeys = translate.seqKeys(cmdKeys)
        identKeys = translate.identKeys(cmdKeys)
        __, duplicate = translate.spsExposureKeys(cmdKeys, doRaise=False)
        lampsKeys = translate.lampsKeys(cmdKeys)
        positions = translate.ditheredFlatsKeys(cmdKeys)

        cams = iicActor.engine.resourceManager.spsConfig.identify(**identKeys)

        return cls(cams, lampsKeys, positions, duplicate, **seqKeys)


class ScienceArc(Arcs):
    """ Biases sequence """
    seqtype = 'scienceArc'
    doScienceCheck = True


class ScienceTrace(Flats):
    """ Biases sequence """
    seqtype = 'scienceTrace'
    doScienceCheck = True


class DomeFlat(SpsSequence):
    """ Biases sequence """
    seqtype = 'domeFlat'
    doScienceCheck = True

    def __init__(self, cams, exptime, duplicate, windowKeys, **seqKeys):
        SpsSequence.__init__(self, cams, isWindowed=bool(windowKeys), **seqKeys)

        self.expose('domeflat', exptime, cams, duplicate=duplicate, windowKeys=windowKeys)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        seqKeys = translate.seqKeys(cmdKeys)
        identKeys = translate.identKeys(cmdKeys)
        exptime, duplicate = translate.spsExposureKeys(cmdKeys)
        windowKeys = translate.windowKeys(cmdKeys)

        cams = iicActor.engine.resourceManager.spsConfig.identify(**identKeys)

        return cls(cams, exptime, duplicate, windowKeys, **seqKeys)
