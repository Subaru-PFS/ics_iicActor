from ics.iicActor.utils.sequencing import Sequence, Loop
from pfs.utils.ncaplar import defocused_exposure_times_single_position


class Object(Sequence):
    """ Simple exposure sequence """
    seqtype = 'scienceObject'
    doCheckFocus = True

    def __init__(self, exptime, duplicate, cams, doTest=False, **kwargs):
        Sequence.__init__(self, **kwargs)
        self.expose(exptype='object', exptime=exptime, cams=cams, duplicate=duplicate, doTest=doTest)

class ObjectLoop(Loop):
    """ Simple exposure sequence """
    seqtype = 'scienceObject'
    doCheckFocus = True

    def __init__(self, exptime, cams, doTest=False, **kwargs):
        Sequence.__init__(self, **kwargs)
        self.expose(exptype='object', exptime=exptime, cams=cams, duplicate=1, doTest=doTest)


class ObjectInterleavedBiasLoop(Loop):
    """ Simple exposure sequence """
    seqtype = 'scienceObject'
    doCheckFocus = True

    def __init__(self, exptime, cams, doTest=False, **kwargs):
        Sequence.__init__(self, **kwargs)
        self.finalBias = True
        self.expose(exptype='bias', cams=cams, duplicate=1, doTest=doTest)
        self.expose(exptype='object', exptime=exptime, cams=cams, duplicate=1, doTest=doTest)

    def commandLogic(self, cmd):
        """ loop the command until being told to stop, store in database"""
        [bias, object] = self.cmdList
        subCmd = None
        try:
            while True:
                for subCmd in [bias, object]:
                    self.processSubCmd(cmd, subCmd=subCmd)
                    if self.doFinish or self.doAbort:
                        raise StopIteration
                    self.archiveAndReset(cmd, subCmd)

        except StopIteration:
            if self.finalBias and subCmd != bias:
                self.processSubCmd(cmd, subCmd=bias)

    def finish(self, cmd, noSunssBias=False):
        """ Finish current sequence """
        self.finalBias = not noSunssBias
        Loop.finish(self, cmd=cmd)


class DomeFlat(Sequence):
    """ Flat/fiberTrace from Dome illumination. """
    seqtype = 'domeFlat'
    doCheckFocus = True

    def __init__(self, exptime, duplicate, cams, doTest=False, **kwargs):
        Sequence.__init__(self, **kwargs)
        self.expose(exptype='domeflat', exptime=exptime, cams=cams, duplicate=duplicate, doTest=doTest)


class Biases(Sequence):
    """ Biases sequence """
    seqtype = 'biases'
    lightBeam = False

    def __init__(self, duplicate, cams, doTest=False, **kwargs):
        Sequence.__init__(self, **kwargs)
        self.expose(exptype='bias', cams=cams, duplicate=duplicate, doTest=doTest)


class Darks(Sequence):
    """ Darks sequence """
    seqtype = 'darks'
    lightBeam = False

    def __init__(self, exptime, duplicate, cams, doTest=False, **kwargs):
        Sequence.__init__(self, **kwargs)
        self.expose(exptype='dark', exptime=exptime, cams=cams, duplicate=duplicate, doTest=doTest)


class Arcs(Sequence):
    """ Arcs sequence """
    seqtype = 'arcs'

    def __init__(self, exptime, duplicate, cams, dcbOn, dcbOff, doTest=False, **kwargs):
        Sequence.__init__(self, **kwargs)

        if any(dcbOn.values()):
            self.head.add(actor='dcb', cmdStr='arc', **dcbOn)

        if any(dcbOff.values()):
            self.tail.add(index=0, actor='dcb', cmdStr='arc', **dcbOff)

        self.expose(exptype='arc', exptime=exptime, cams=cams, duplicate=duplicate, doTest=doTest)


class Flats(Sequence):
    """ Flat / fiberTrace sequence """
    seqtype = 'flats'

    def __init__(self, exptime, duplicate, cams, dcbOn, dcbOff, doTest=False, **kwargs):
        Sequence.__init__(self, **kwargs)

        if any(dcbOn.values()):
            self.head.add(actor='dcb', cmdStr='arc', **dcbOn)

        if any(dcbOff.values()):
            self.tail.add(index=0, actor='dcb', cmdStr='arc', **dcbOff)
        self.expose(exptype='flat', exptime=exptime, cams=cams, duplicate=duplicate, doTest=doTest)


class MasterBiases(Biases):
    """ Biases for calibration products """
    seqtype = 'masterBiases'


class MasterDarks(Darks):
    """ Darks for calibration products """
    seqtype = 'masterDarks'


class ScienceArc(Arcs):
    """ In-focus arcs """
    seqtype = 'scienceArc'
    doCheckFocus = True


class ScienceTrace(Flats):
    """ In-focus flat/fiberTrace"""
    seqtype = 'scienceTrace'
    doCheckFocus = True


class SlitThroughFocus(Sequence):
    """ Slit through focus sequence """
    seqtype = 'slitThroughFocus'

    def __init__(self, exptime, positions, duplicate, cams, dcbOn, dcbOff, doTest=False, **kwargs):
        Sequence.__init__(self, **kwargs)

        if any(dcbOn.values()):
            self.head.add(actor='dcb', cmdStr='arc', **dcbOn)

        if any(dcbOff.values()):
            self.tail.add(index=0, actor='dcb', cmdStr='arc', **dcbOff)

        for position in positions:
            self.add(actor='sps', cmdStr='slit', focus=position, abs=True, cams=cams)
            self.expose(exptype='arc', exptime=exptime, cams='{cams}', duplicate=duplicate, doTest=doTest)

        self.tail.add(actor='sps', cmdStr='slit', focus=0, abs=True, cams=cams)


class DetThroughFocus(Sequence):
    """ Detector through focus sequence """
    seqtype = 'detThroughFocus'

    def __init__(self, exptime, positions, duplicate, cams, dcbOn, dcbOff, doTest=False, **kwargs):
        Sequence.__init__(self, **kwargs)

        if any(dcbOn.values()):
            self.head.add(actor='dcb', cmdStr='arc', **dcbOn)

        if any(dcbOff.values()):
            self.tail.add(index=0, actor='dcb', cmdStr='arc', **dcbOff)

        for motorA, motorB, motorC in positions:
            self.add(actor='sps', cmdStr='ccdMotors move',
                     a=motorA, b=motorB, c=motorC, microns=True, abs=True, cams=cams)
            self.expose(exptype='arc', exptime=exptime, cams='{cams}', duplicate=duplicate, doTest=doTest)


class DitheredFlats(Sequence):
    """ Dithered Flats sequence """
    seqtype = 'ditheredFlats'

    def __init__(self, exptime, positions, duplicate, cams, dcbOn, dcbOff, doTest=False, **kwargs):
        Sequence.__init__(self, **kwargs)

        if any(dcbOn.values()):
            self.head.add(actor='dcb', cmdStr='arc', **dcbOn)

        if any(dcbOff.values()):
            self.tail.add(index=0, actor='dcb', cmdStr='arc', **dcbOff)

        self.add(actor='sps', cmdStr='slit dither', x=0, pixels=True, abs=True, cams=cams)
        self.expose(exptype='flat', exptime=exptime, cams='{cams}', duplicate=duplicate, doTest=doTest)

        for position in positions:
            self.add(actor='sps', cmdStr='slit dither', x=position, pixels=True, abs=True, cams=cams)
            self.expose(exptype='flat', exptime=exptime, cams='{cams}', duplicate=duplicate, doTest=doTest)

        self.add(actor='sps', cmdStr='slit dither', x=0, pixels=True, abs=True, cams=cams)
        self.expose(exptype='flat', exptime=exptime, cams='{cams}', duplicate=duplicate, doTest=doTest)

        self.tail.add(actor='sps', cmdStr='slit dither', x=0, y=0, pixels=True, abs=True, cams=cams)


class DitheredArcs(Sequence):
    """ Dithered Arcs sequence """
    seqtype = 'ditheredArcs'

    def __init__(self, exptime, pixels, doMinus, duplicate, cams, dcbOn, dcbOff, doTest=False, **kwargs):
        Sequence.__init__(self, **kwargs)

        if any(dcbOn.values()):
            self.head.add(actor='dcb', cmdStr='arc', **dcbOn)

        if any(dcbOff.values()):
            self.tail.add(index=0, actor='dcb', cmdStr='arc', **dcbOff)

        end = int(1 / pixels)
        start = -end + 1 if doMinus else 0
        for x in range(start, end):
            for y in range(start, end):
                self.add(actor='sps', cmdStr='slit dither',
                         x=x * pixels, y=y * pixels, pixels=True, abs=True, cams=cams)
                self.expose(exptype='arc', exptime=exptime, cams='{cams}', duplicate=duplicate, doTest=doTest)

        self.tail.add(actor='sps', cmdStr='slit dither', x=0, y=0, pixels=True, abs=True, cams=cams)


class DefocusedArcs(Sequence):
    """ Defocus sequence """
    seqtype = 'defocusedArcs'

    def __init__(self, exp_time_0, positions, duplicate, cams, dcbOn, dcbOff, doTest=False, **kwargs):
        Sequence.__init__(self, **kwargs)
        att_value_0 = dcbOn['attenuator']

        if any(dcbOn.values()):
            self.head.add(actor='dcb', cmdStr='arc', **dcbOn)

        if any(dcbOff.values()):
            self.tail.add(index=0, actor='dcb', cmdStr='arc', **dcbOff)

        for position in positions:
            exptime, attenuator = defocused_exposure_times_single_position(exp_time_0=exp_time_0[0],
                                                                           att_value_0=att_value_0,
                                                                           defocused_value=position)
            if att_value_0 is not None:
                self.add(actor='dcb', cmdStr='arc', attenuator=attenuator, timeLim=300)

            self.add(actor='sps', cmdStr='slit', focus=position, abs=True, cams=cams)
            self.expose(exptype='arc', exptime=exptime, cams='{cams}', duplicate=duplicate, doTest=doTest)

        self.tail.add(actor='sps', cmdStr='slit', focus=0, abs=True, cams=cams)


class Custom(Sequence):
    """ Custom sequence """
    seqtype = 'custom'

    def __init__(self, duplicate, cams, doTest=False, **kwargs):
        Sequence.__init__(self, **kwargs)
