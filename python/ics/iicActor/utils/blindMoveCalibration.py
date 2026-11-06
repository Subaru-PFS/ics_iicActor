class BlindMoveCalibration:
    """One operating-point blind-move calibration in progress: its plan, fixed at start, and
    what is done.

    The plan is a turned black-dot design and the runs of each iteration and of the
    validation.  Every run lands at fps' landing depth and pushes to its target.  The first
    iteration's runs are commanded through the motor map alone; each next iteration's are
    aimed, landing and push, through the calibration fps calibrateBlindMove operatingPoint
    fits on the iteration before.  The last iteration's calibration is the session's: its
    validation runs are aimed through it, then fps validateBlindMove judges them.

    Progress is the visits and the calibration fitted of each iteration, and the validation
    visits, so a sequence that stopped can be continued from the first step not done.  A
    session that only validates has no iteration and the calibration it was given.
    """

    def __init__(self, designId, runConfig, seqKeys, nRuns=(), nValidationRuns=0, nRetries=0,
                 calibId=None):
        self.designId = designId
        self.runConfig = dict(runConfig)
        self.seqKeys = dict(seqKeys)
        self.planned = [int(n) for n in nRuns]
        self.nValidationRuns = int(nValidationRuns)
        self.nRetries = int(nRetries)

        self.visits = [[] for _ in self.planned]
        self.fitted = [None for _ in self.planned]
        self.validationVisits = []
        self.givenCalibId = calibId
        self.validated = False

    @property
    def calibId(self):
        """The calibration the validation judges: the last iteration's, or the one given."""
        return self.fitted[-1] if self.planned else self.givenCalibId

    def aimedThrough(self, iteration):
        """The calibration the runs of `iteration` are aimed through; None at the motor map."""
        return None if iteration == 0 else self.fitted[iteration - 1]

    def newValidation(self, nRuns):
        """Discard the validation runs so far: the next `nRuns` start a fresh validation."""
        self.nValidationRuns = int(nRuns)
        self.validationVisits = []
        self.validated = False

    def __str__(self):
        steps = [f'iteration {i + 1} {len(v)}/{n}' + ('' if c is None else f' (calibration {c})')
                 for i, (v, n, c) in enumerate(zip(self.visits, self.planned, self.fitted))]
        if self.nValidationRuns:
            steps.append(f'validation {len(self.validationVisits)}/{self.nValidationRuns}')
        calib = 'not fitted' if self.calibId is None else f'calibration {self.calibId}'
        return f'{", ".join(steps)}; {calib}, {"validated" if self.validated else "not validated"}'
