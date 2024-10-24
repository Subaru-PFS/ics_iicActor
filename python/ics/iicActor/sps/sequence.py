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

        sequence.Sequence.__init__(self, *args, **kwargs)
        self.seqtype = f'{self.seqtype}_windowed' if isWindowed else self.seqtype

    @property
    def allLightSources(self):
        return list(set([cam.lightSource for cam in self.cams]))

    @property
    def lightSource(self):
        """Get light source from our sets of specs."""
        if len(self.allLightSources) > 1:
            raise RuntimeError('there can only be one light source for a given sequence')

        return self.allLightSources[0]

    @property
    def isPfiExposure(self):
        return 'pfi' in self.allLightSources

    def matchPfsConfigArms(self, pfsConfigArms):
        """
        Match the arms in the current pfsConfig to the arms being used in the sequence.

        Parameters
        ----------
        pfsConfig : `pfs.datamodel.pfsConfig.PfsConfig`
            Current pfsConfig.

        Returns
        -------
        str
            The arms being used in the sequence, as a string.

        Raises
        ------
        ValueError
            If any of the arms being used in the sequence are not present in the pfsConfig and
            `forceGrating` is set to `False`.
        """
        useArms = set([self.engine.keyRepo.getActualArm(cam) for cam in self.cams])
        diffArm = useArms - set(pfsConfigArms)

        if len(diffArm) and not self.forceGrating:
            raise ValueError(f"{','.join(diffArm)} not present in pfsConfig.arms")

        return ''.join(useArms)

    def expose(self, exptype, exptime, cams, duplicate=1, windowKeys=None, slideSlit=None):
        """Append duplicate * sps expose to sequence."""
        # being nice about input arguments.
        exptime = [exptime] if not isinstance(exptime, list) else exptime
        windowKeys = dict() if windowKeys is None else windowKeys

        # instantiating for each exptime/duplicate.
        for expTime in exptime:
            for nExposure in range(duplicate):
                # creating SpsExpose command object.
                spsExpose = SpsExpose.specify(self, exptype, expTime, cams,
                                              doTest=self.doTest, doScienceCheck=self.doScienceCheck,
                                              slideSlit=slideSlit, **windowKeys)
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

    def match(self, filter):
        """do that sequence match the filter."""
        doMatch = 'sunss' in self.allLightSources if filter == 'sunss' else True

        return doMatch
