class BlindMoveCalibration:
    """One blind-move calibration in progress: its plan, fixed at start, and what is done.

    The plan is a turned black-dot design, the depths of the calibration runs in order,
    and those of the validation runs.  Progress is the visits of the runs that completed,
    the calibration fps fitted from them, and whether it was validated, so a sequence that
    stopped can be continued from the first step not done.
    """

    def __init__(self, designId, calibrationTargets, validationTargets, runConfig, seqKeys,
                 nRetries=0, calibId=None):
        self.designId = designId
        self.calibrationTargets = list(calibrationTargets)
        self.validationTargets = list(validationTargets)
        self.runConfig = dict(runConfig)
        self.seqKeys = dict(seqKeys)
        self.nRetries = int(nRetries)

        self.calibrationVisits = []
        self.calibId = calibId
        self.validationVisits = []
        self.validated = False

    @property
    def remainingCalibration(self):
        """Depths of the calibration runs still to take, in order."""
        return self.calibrationTargets[len(self.calibrationVisits):]

    @property
    def remainingValidation(self):
        """Depths of the validation runs still to take, in order."""
        return self.validationTargets[len(self.validationVisits):]

    def newValidation(self):
        """Discard the validation runs so far: the next ones start a fresh validation."""
        self.validationVisits = []
        self.validated = False

    def __str__(self):
        calib = 'not fitted' if self.calibId is None else f'calibration {self.calibId}'
        if self.calibrationTargets:
            done = f'{len(self.calibrationVisits)}/{len(self.calibrationTargets)} calibration runs, '
        else:
            done = ''
        return (f'{done}{calib}, {len(self.validationVisits)}/{len(self.validationTargets)} '
                f'validation runs, {"validated" if self.validated else "not validated"}')
