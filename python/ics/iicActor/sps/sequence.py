import ics.utils.cmd as cmdUtils
import iicActor.utils.sequence as sequence
from ics.iicActor.sps.subcmd import SpsExpose, DcbCmd, LampsCmd
from ics.iicActor.utils.subcmd import SubCmd


class SpsSequence(sequence.Sequence):
    lightBeam = True
    shutterRequired = True
    doScienceCheck = False
    """"""

    def __init__(self, cams, *args, isWindowed=False, **kwargs):
        self.cams = cams
        self.lightSource = self.getLightSource(cams)

        sequence.Sequence.__init__(self, *args, **kwargs)
        self.seqtype = f'{self.seqtype}_windowed' if isWindowed else self.seqtype

    def getLightSource(self, cams):
        """Get light source from our sets of specs."""
        # easy in that case.
        if not self.lightBeam:
            return 'None'

        try:
            [lightSource] = list(set([cam.lightSource for cam in cams]))
        except:
            raise RuntimeError('there can only be one light source for a given sequence')

        return lightSource

    def expose(self, exptype, exptime, cams, duplicate=1, windowKeys=None):
        """Append duplicate * sps expose to sequence."""
        # being nice about input arguments.
        exptime = [exptime] if not isinstance(exptime, list) else exptime
        windowKeys = dict() if windowKeys is None else windowKeys

        # instantiating for each exptime/duplicate.
        for expTime in exptime:
            for nExposure in range(duplicate):
                # creating SpsExpose command object.
                spsExpose = SpsExpose.specify(self, exptype, expTime, cams,
                                              doTest=self.doTest, doScienceCheck=self.doScienceCheck, **windowKeys)
                list.append(self, spsExpose)

    def instantiate(self, actor, cmdStr, **kwargs):
        """Return right SubCmd type based on actor/cmdStr."""
        # this is called by add function.
        if actor == 'lamps':
            cls = LampsCmd
        elif 'dcb' in actor:
            cls = DcbCmd
        # I always call expose(), so this should never be called and might fail or might work, leaving there for now.
        elif actor == 'sps' and 'expose' in cmdStr:
            cls = SpsExpose
        else:
            cls = SubCmd

        return cls(self, actor, cmdStr, **kwargs)

    def guessTimeOffset(self, subCmd):
        """This is sketchy but only called by head or tail, so okay."""
        timeOffset = 0

        # find those arguments that can extend command above timeout.
        for key in ['warmingTime', 'exptime']:
            value = cmdUtils.findCmdKeyValue(subCmd.cmdStr, cmdKey=key)
            timeOffset = max(float(value), timeOffset) if value is not None else timeOffset

        # We know very well those can take a while, not taking risk here.
        if 'rexm' in subCmd.cmdStr or 'rda' in subCmd.cmdStr:
            timeOffset = max(timeOffset, 120)

        return timeOffset
