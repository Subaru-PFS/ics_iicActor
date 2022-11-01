import iicActor.utils.translate as translate
import numpy as np
from ics.iicActor.sps.sequence import SpsSequence
from ics.iicActor.utils.sequence import Sequence


class HexapodStability(SpsSequence):
    """ hexapod stability sequence """
    seqtype = 'hexapodStability'

    def __init__(self, cams, lampsKeys, duplicate, positions, **seqKeys):
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
        SpsSequence.__init__(self, cams, **seqKeys)
        # taking an exposure before turning on slit
        self.expose('arc', lampsKeys, cams, duplicate=duplicate)
        self.add('sps', 'slit start', cams=cams)

        # taking one exposure in home.
        self.add('sps', 'slit home', cams=cams)
        self.expose('arc', lampsKeys, cams, duplicate=duplicate)

        for pos in positions:
            # Move y once separately
            self.add('sps', 'slit dither', y=round(pos, 5), abs=True, cams=cams)
            for pos in positions:
                self.add('sps', 'slit dither', x=round(pos, 5), abs=True, cams=cams)
                self.expose('arc', lampsKeys, cams, duplicate=duplicate)

        # taking again an exposure in home
        self.add('sps', 'slit home', cams=cams)
        self.expose('arc', lampsKeys, cams, duplicate=duplicate)

        # taking an exposure after hexapod is turned back off.
        self.add('sps', 'slit stop', cams=cams)
        self.expose('arc', lampsKeys, cams, duplicate=duplicate)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        seqKeys = translate.seqKeys(cmdKeys)
        identKeys = translate.identKeys(cmdKeys)
        __, duplicate = translate.spsExposureKeys(cmdKeys, doRaise=False)
        lampsKeys = translate.lampsKeys(cmdKeys)

        # taking at least 3 exposure.
        duplicate = max(duplicate, 3)

        # setting default step to 10 microns, note that positions are reversed.
        [start, stop, step] = cmdKeys['position'].values if 'position' in cmdKeys else [-0.05, 0.055, 0.01]
        positions = np.arange(start, stop, step)[::-1]

        cams = iicActor.engine.resourceManager.spsConfig.identify(**identKeys)

        return cls(cams, lampsKeys, duplicate, positions, **seqKeys)


class RdaMove(Sequence):
    """ Rda move sequence """
    seqtype = 'rdaMove'

    def __init__(self, specModules, targetPosition, **seqKeys):
        Sequence.__init__(self, **seqKeys)
        specNums = [specModule.specNum for specModule in specModules]
        self.add('sps', f'rda moveTo {targetPosition}', specNums=','.join(map(str, specNums)), timeLim=180)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct MasterBiases object."""
        seqKeys = translate.seqKeys(cmdKeys)
        identKeys = translate.identKeys(cmdKeys)
        specModules = iicActor.engine.resourceManager.spsConfig.selectModules(identKeys['specNums'])
        targetPosition = 'low' if 'low' in cmdKeys else 'med'

        return cls(specModules, targetPosition, **seqKeys)

    @classmethod
    def fromDesign(cls, iicActor, targetPosition):
        """Defining rules to construct MasterBiases object."""
        specModules = iicActor.engine.resourceManager.spsConfig.selectModules(None)
        return cls(specModules, targetPosition)
