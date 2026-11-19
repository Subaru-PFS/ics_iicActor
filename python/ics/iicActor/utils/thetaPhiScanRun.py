import ics.iicActor.utils.lib as iicUtils


class ThetaPhiScanRun:
    """One angle of a thetaPhiScan in progress: its plan, fixed at start, and what is done.

    The cobras hold `constantAngle` on `constantAxis` while the other axis, the inner one,
    steps through `innerAngles`, 0 standing for the inner axis at home.  The scan starts with
    every cobra at home and a cobraHome trace, then, for each inner angle, moves the cobras to
    that angle's design and takes a trace there.

    Progress is the cobraHome trace and the inner angles traced, so a scan that stopped can be
    continued from the first step not done.

    Parameters
    ----------
    groupId : `int`
        Sequence group of the scan.
    constantAxis : `str`
        'theta' or 'phi'.
    constantAngle : `int`
        [deg] angle held on `constantAxis`.
    innerAngles : `list` of `int`
        [deg] inner-axis angles, in the order they are scanned; 0 is the inner axis at home.
    traceKeys : `dict`
        cams, lampsKeys, duplicate and windowKeys of every scienceTrace.
    moveConfig : `dict`
        Keywords of every MoveToPfsDesign.
    """

    def __init__(self, groupId, constantAxis, constantAngle, innerAngles, traceKeys, moveConfig):
        self.groupId = groupId
        self.constantAxis = constantAxis
        self.constantAngle = int(constantAngle)
        self.innerAngles = [int(angle) for angle in innerAngles]
        self.traceKeys = dict(traceKeys)
        self.moveConfig = dict(moveConfig)

        self.homeTraced = False
        self.traced = []

    @property
    def innerAxis(self):
        return 'phi' if self.constantAxis == 'theta' else 'theta'

    @property
    def name(self):
        """iic_sequence.name of every trace of the scan."""
        return f'{self.constantAxis}_{self.constantAngle:03d}'

    @property
    def remaining(self):
        """Inner angles not traced yet, in scan order."""
        return [angle for angle in self.innerAngles if angle not in self.traced]

    @property
    def isDone(self):
        return self.homeTraced and not self.remaining

    def angles(self, innerAngle):
        """(thetaAngle, phiAngle) of the cobras at `innerAngle`."""
        if self.constantAxis == 'theta':
            return self.constantAngle, innerAngle
        return innerAngle, self.constantAngle

    def designName(self, innerAngle):
        """Name of the design of `innerAngle`, also the comments of its trace."""
        thetaAngle, phiAngle = self.angles(innerAngle)
        return iicUtils.thetaPhiScanDesignName(thetaAngle, phiAngle,
                                               atHome=self.innerAxis if innerAngle == 0 else None)

    def __str__(self):
        home = 'cobraHome traced' if self.homeTraced else 'cobraHome not traced'
        return (f'thetaPhiScan groupId={self.groupId} {self.constantAxis}Angle={self.constantAngle}: {home}, '
                f'{len(self.traced)}/{len(self.innerAngles)} {self.innerAxis} angles traced')
