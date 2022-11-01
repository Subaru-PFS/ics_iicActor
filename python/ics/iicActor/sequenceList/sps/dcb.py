import iicActor.utils.translate as translate
import numpy as np
from ics.iicActor.sps.sequence import SpsSequence
from ics.utils.sps.defocus import defocused_exposure_times_single_position


class DitheredFlats(SpsSequence):
    """ Dithered Flats sequence """
    seqtype = 'ditheredFlats'

    def __init__(self, cams, exptime, dcbOn, dcbOff, positions, duplicate, **seqKeys):
        SpsSequence.__init__(self, cams, **seqKeys)

        # adding dcbOn and dcbOff commands.
        if any(dcbOn.values()):
            self.head.add('dcb', 'lamps', **dcbOn)

        if any(dcbOff.values()):
            self.tail.add('dcb', 'lamps', **dcbOff)

        # taking a trace before starting hexapod.
        self.expose('flat', exptime, cams, duplicate=duplicate)
        self.add('sps', 'slit start', cams=cams)

        # taking a trace in home to start.
        self.add('sps', 'slit home', cams=cams)
        self.expose('flat', exptime, cams, duplicate=duplicate)

        for position in positions:
            self.add('sps', 'slit dither', x=position, pixels=True, abs=True, cams=cams)
            self.expose('flat', exptime, cams, duplicate=duplicate)

        # taking a trace in home to end.
        self.add('sps', 'slit home', cams=cams)
        self.expose('flat', exptime, cams, duplicate=duplicate)

        # taking a trace after the hexapod is turned back off.
        self.add('sps', 'slit stop', cams=cams)
        self.expose('flat', exptime, cams, duplicate=duplicate)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        seqKeys = translate.seqKeys(cmdKeys)
        identKeys = translate.identKeys(cmdKeys)
        exptime, duplicate = translate.spsExposureKeys(cmdKeys)
        dcbOn, dcbOff = translate.dcbKeys(cmdKeys)
        positions = translate.ditheredFlatsKeys(cmdKeys)

        cams = iicActor.engine.resourceManager.spsConfig.identify(**identKeys)

        return cls(cams, exptime, dcbOn, dcbOff, positions, duplicate, **seqKeys)


class Arcs(SpsSequence):
    """ Biases sequence """
    seqtype = 'arcs'

    def __init__(self, cams, exptime, dcbOn, dcbOff, duplicate, **seqKeys):
        SpsSequence.__init__(self, cams, **seqKeys)

        # adding dcbOn and dcbOff commands.
        if any(dcbOn.values()):
            self.head.add('dcb', 'lamps', **dcbOn)

        if any(dcbOff.values()):
            self.tail.add('dcb', 'lamps', **dcbOff)

        self.expose('arc', exptime, cams, duplicate=duplicate)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        seqKeys = translate.seqKeys(cmdKeys)
        identKeys = translate.identKeys(cmdKeys)
        exptime, duplicate = translate.spsExposureKeys(cmdKeys)
        dcbOn, dcbOff = translate.dcbKeys(cmdKeys)

        cams = iicActor.engine.resourceManager.spsConfig.identify(**identKeys)

        return cls(cams, exptime, dcbOn, dcbOff, duplicate, **seqKeys)


class Flats(SpsSequence):
    """ Biases sequence """
    seqtype = 'flats'

    def __init__(self, cams, exptime, dcbOn, dcbOff, duplicate, windowKeys, **seqKeys):
        SpsSequence.__init__(self, cams, isWindowed=bool(windowKeys), **seqKeys)

        # adding dcbOn and dcbOff commands.
        if any(dcbOn.values()):
            self.head.add('dcb', 'lamps', **dcbOn)

        if any(dcbOff.values()):
            self.tail.add('dcb', 'lamps', **dcbOff)

        self.expose('flat', exptime, cams, duplicate=duplicate, windowKeys=windowKeys)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        seqKeys = translate.seqKeys(cmdKeys)
        identKeys = translate.identKeys(cmdKeys)
        exptime, duplicate = translate.spsExposureKeys(cmdKeys)
        windowKeys = translate.windowKeys(cmdKeys)
        dcbOn, dcbOff = translate.dcbKeys(cmdKeys, forceHalogen=True)

        cams = iicActor.engine.resourceManager.spsConfig.identify(**identKeys)

        return cls(cams, exptime, dcbOn, dcbOff, duplicate, windowKeys, **seqKeys)


class ScienceArc(Arcs):
    """ Biases sequence """
    seqtype = 'scienceArc'
    doScienceCheck = True


class ScienceTrace(Flats):
    """ Biases sequence """
    seqtype = 'scienceTrace'
    doScienceCheck = True


class DitheredArcs(SpsSequence):
    """ Dithered Arcs sequence """
    seqtype = 'ditheredArcs'

    def __init__(self, cams, exptime, dcbOn, dcbOff, duplicate, pixelStep, **seqKeys):
        SpsSequence.__init__(self, cams, **seqKeys)

        # adding dcbOn and dcbOff commands.
        if any(dcbOn.values()):
            self.head.add('dcb', 'lamps', **dcbOn)

        if any(dcbOff.values()):
            self.tail.add('dcb', 'lamps', **dcbOff)

        # start hexapod and move home.
        self.add('sps', 'slit start', cams=cams)
        self.add('sps', 'slit home', cams=cams)

        end = int(1 / pixelStep)
        start = 0
        for x in range(start, end):
            for y in range(start, end):
                xPix, yPix = x * pixelStep, y * pixelStep
                self.add('sps', 'slit dither', x=xPix, y=yPix, pixels=True, abs=True, cams=cams)
                self.expose('arc', exptime, cams, duplicate=duplicate)

        # move back home and stop hexapod.
        self.add('sps', 'slit home', cams=cams)
        self.add('sps', 'slit stop', cams=cams)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        seqKeys = translate.seqKeys(cmdKeys)
        identKeys = translate.identKeys(cmdKeys)
        exptime, duplicate = translate.spsExposureKeys(cmdKeys)
        dcbOn, dcbOff = translate.dcbKeys(cmdKeys)
        pixelStep = cmdKeys['pixelStep'].values[0]

        cams = iicActor.engine.resourceManager.spsConfig.identify(**identKeys)

        return cls(cams, exptime, dcbOn, dcbOff, duplicate, pixelStep, **seqKeys)


class DetThroughFocus(SpsSequence):
    """ Detector through focus sequence """
    seqtype = 'detThroughFocus'

    def __init__(self, cams, exptime, dcbOn, dcbOff, duplicate, positions, **seqKeys):
        SpsSequence.__init__(self, cams, **seqKeys)

        # adding dcbOn and dcbOff commands.
        if any(dcbOn.values()):
            self.head.add('dcb', 'lamps', **dcbOn)

        if any(dcbOff.values()):
            self.tail.add('dcb', 'lamps', **dcbOff)

        for motorA, motorB, motorC in positions:
            self.add('sps', 'ccdMotors move', a=motorA, b=motorB, c=motorC, microns=True, abs=True, cams=cams)
            self.expose('arc', exptime, cams, duplicate=duplicate)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        seqKeys = translate.seqKeys(cmdKeys)
        identKeys = translate.identKeys(cmdKeys)
        exptime, duplicate = translate.spsExposureKeys(cmdKeys)
        dcbOn, dcbOff = translate.dcbKeys(cmdKeys)
        # translating from given position and tilt.
        positions = translate.detThroughFocusKeys(cmdKeys)

        cams = iicActor.engine.resourceManager.spsConfig.identify(**identKeys)

        return cls(cams, exptime, dcbOn, dcbOff, duplicate, positions, **seqKeys)


class DefocusedArcs(SpsSequence):
    """ Defocus sequence """
    seqtype = 'defocusedArcs'

    def __init__(self, cams, exptime, dcbOn, dcbOff, duplicate, positions, **seqKeys):
        SpsSequence.__init__(self, cams, **seqKeys)

        # adding dcbOn and dcbOff commands.
        if any(dcbOn.values()):
            self.head.add('dcb', 'lamps', **dcbOn)

        if any(dcbOff.values()):
            self.tail.add('dcb', 'lamps', **dcbOff)

        # start hexapod and move home.
        self.add('sps', 'slit start', cams=cams)
        self.add('sps', 'slit home', cams=cams)

        for position in positions:
            multFactor, _ = defocused_exposure_times_single_position(exp_time_0=1, att_value_0=None,
                                                                     defocused_value=position)
            scaled = [expTime * multFactor for expTime in exptime]

            self.add('sps', 'slit', focus=position, abs=True, cams=cams)
            self.expose('arc', scaled, cams, duplicate=duplicate)

        # move back home and stop hexapod.
        self.add('sps', 'slit home', cams=cams)
        self.add('sps', 'slit stop', cams=cams)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        seqKeys = translate.seqKeys(cmdKeys)
        identKeys = translate.identKeys(cmdKeys)
        exptime, duplicate = translate.spsExposureKeys(cmdKeys)
        dcbOn, dcbOff = translate.dcbKeys(cmdKeys)
        # basic np.linspace.
        start, stop, num = cmdKeys['position'].values
        positions = np.linspace(start, stop, num=int(num)).round(6)

        cams = iicActor.engine.resourceManager.spsConfig.identify(**identKeys)

        return cls(cams, exptime, dcbOn, dcbOff, duplicate, positions, **seqKeys)
