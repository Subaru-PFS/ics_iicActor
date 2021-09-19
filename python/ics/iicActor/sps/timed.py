import ics.iicActor.sps.sequenceList as spsSequence
from ics.iicActor.sps.sequence import SpsSequence
from ics.iicActor.sps.subcmd import SpsExpose
from pfs.utils.ncaplar import defocused_exposure_times_single_position


class timedLampsSequence(SpsSequence):
    shutterRequired = False

    def expose(self, exptype, exptime=0.0, duplicate=1, doTest=False, **identKeys):
        """ Append duplicate * sps expose to sequence """

        def doTimedLamps(timedLamps):
            exptime = 0.0
            lamps = []

            for lamp in ['argon', 'hgcd', 'hgar', 'krypton', 'neon', 'xenon', 'halogen']:
                if lamp in timedLamps.keys():
                    exptime = max(exptime, timedLamps[lamp])
                    lamps.append(f"{lamp}={timedLamps[lamp]}")
            return exptime, f'prepare {" ".join(lamps)}'

        shutterTiming = exptime['shutterTiming']
        doLampsTiming = not shutterTiming
        exptime, lampsCmdStr = doTimedLamps(exptime)

        for i in range(duplicate):
            timeOffset = 240 if 'hgcd' in lampsCmdStr else 120
            self.add(actor='lamps', cmdStr=lampsCmdStr)
            if doLampsTiming:
                self.append(SpsExpose.specify(exptype, exptime,
                                              doLamps=True, timeOffset=timeOffset, doTest=doTest, **identKeys))
            else:
                self.add(actor='lamps', cmdStr='go noWait', idleTime=2)
                self.append(SpsExpose.specify(exptype, shutterTiming, doTest=doTest, **identKeys))


class ScienceArc(spsSequence.ScienceArc, timedLampsSequence):
    """"""


class ScienceTrace(spsSequence.ScienceTrace, timedLampsSequence):
    """"""


class Arcs(spsSequence.Arcs, timedLampsSequence):
    """"""


class Flats(spsSequence.Flats, timedLampsSequence):
    """"""


class SlitThroughFocus(spsSequence.SlitThroughFocus, timedLampsSequence):
    """"""


class DetThroughFocus(spsSequence.DetThroughFocus, timedLampsSequence):
    """"""


class DitheredArcs(spsSequence.DitheredArcs, timedLampsSequence):
    """"""


class DitheredFlats(spsSequence.DitheredFlats, timedLampsSequence):
    """"""


class HexapodStability(SpsSequence):
    """ hexapod stability sequence """

    def __init__(self, position, duplicate, cams, timedLamps, doTest=False, **kwargs):
        """Acquire a hexapod repeatability grid.

        Args
        ----
        positions : vector of `float`
          the positions for the slit dither and shift grid.
          Default=[0.05, 0.04, 0.03, 0.02, 0.01, 0, -0.01, -0.02, -0.03, -0.04, -0.05]
        duplicate : `int`
          the number of exposures to take at each position.

        Notes
        -----
        The cams/sm needs to be worked out:
          - with DCB, we can only illuminate one SM, and only the red right now.
          - with pfiLamps, all SMs will be illuminated, but probably still only red.

        """
        SpsSequence.__init__(self, 'hexapodStability', **kwargs)
        if not timedLamps:
            timedLamps = dict(argon=45)

        positions = position[::-1]

        self.add('sps', 'slit', focus=0.0, abs=True)
        self.add('sps', 'slit dither', x=0.0, y=0.0, abs=True, cams=cams)
        self.expose('arc', exptime=timedLamps, cams='{cams}', duplicate=duplicate, doTest=doTest)
        for pos in positions:
            # Move y once separately
            self.add('sps', 'slit dither', y=round(pos, 5), abs=True, cams=cams)
            for pos in positions:
                self.add('sps', f'slit dither', x=round(pos, 5), abs=True, cams=cams)
                self.expose('arc', exptime=timedLamps, cams='{cams}', duplicate=duplicate, doTest=doTest)
        self.add('sps', 'slit dither', x=0.0, y=0.0, abs=True, cams=cams)
        self.expose('arc', exptime=timedLamps, cams='{cams}', duplicate=duplicate, doTest=doTest)


def defocused_exposure_times_no_atten(exp_time_0, defocused_value):
    exptime, __ = defocused_exposure_times_single_position(exp_time_0=exp_time_0, att_value_0=None,
                                                           defocused_value=defocused_value)
    return exptime


class DefocusedArcs(spsSequence.DefocusedArcs, timedLampsSequence):
    """ Defocus sequence """

    def __init__(self, exp_time_0, positions, duplicate, cams, dcbOn, dcbOff, doTest=False, **kwargs):
        SpsSequence.__init__(self, **kwargs)
        timedLamps0 = [(k, v) for k, v in exp_time_0.items()]

        for position in positions:
            calcExptime = [defocused_exposure_times_no_atten(exptime, position) for lamp, exptime in timedLamps0]
            calcTimedLamps = dict([(lamp, exptime) for (lamp, __), exptime in zip(timedLamps0, calcExptime)])
            self.add(actor='sps', cmdStr='slit', focus=position, abs=True, cams=cams)
            self.expose('arc', exptime=calcTimedLamps, cams='{cams}', duplicate=duplicate, doTest=doTest)
