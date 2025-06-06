import ics.utils.cmd as cmdUtils
import iicActor.utils.sequence as sequence
import iicActor.utils.translate as translate
from ics.iicActor.sps.expose import SpsExpose
from ics.iicActor.sps.subcmd import DcbCmd, LampsCmd
from ics.iicActor.utils.subcmd import SubCmd


class SpsSequence(sequence.Sequence):
    lightBeam = True
    shutterRequired = True
    doScienceCheck = False
    """"""

    def __init__(self, cams, *args, isWindowed=False, forceGrating=False, returnWhenShutterClose=False,
                 skipBiaCheck=False, **kwargs):
        self.cams = cams

        sequence.Sequence.__init__(self, *args, **kwargs)

        self.forceGrating = forceGrating
        self.returnWhenShutterClose = returnWhenShutterClose
        self.skipBiaCheck = skipBiaCheck
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

    @property
    def remainingExposures(self):
        return [subCmd for subCmd in self.remainingCmds if isinstance(subCmd, SpsExpose)]

    def initialize(self, engine, cmd):
        """
        Initialize the startup sequence.

        Parameters
        ----------
        engine : object
            The engine instance used to initialize the startup.
        cmd : object
            Command object to be executed.

        Notes
        -----
        Sets default comments if none are provided by fetching selected arms
        and translating them to default comments.
        """
        # Set default comments based on selected arms if not already defined
        if not self.comments:
            selectedArms = engine.keyRepo.getSelectedArms(self.cams)
            self.comments = translate.setDefaultComments(selectedArms)

        super().initialize(engine, cmd)

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
        selectedArms = self.engine.keyRepo.getSelectedArms(self.cams)
        diffArm = selectedArms - set(pfsConfigArms)

        if len(diffArm) and not self.forceGrating:
            raise ValueError(f"{','.join(diffArm)} not present in pfsConfig.arms")

        return ''.join(selectedArms)

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
                                              doTest=self.doTest,
                                              doScienceCheck=self.doScienceCheck, skipBiaCheck=self.skipBiaCheck,
                                              slideSlit=slideSlit, **windowKeys)
                list.append(self, spsExpose)

    @staticmethod
    def keysToCam(iicActor, cmdKeys):
        """Identify the cameras based on the provided command keywords."""
        if iicActor.spsConfig is None:
            raise RuntimeError('Could not figure out spsConfig, please check spsActor...')

        return iicActor.spsConfig.keysToCam(cmdKeys)

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

        if filter == 'sunss':
            doMatch = 'sunss' in self.allLightSources
        elif filter == 'returnWhenShutterClose':
            doMatch = self.returnWhenShutterClose
        else:
            doMatch = True

        return doMatch
