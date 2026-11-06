class BlindMoveCalibration:
    """One operating-point blind-move calibration in progress: its plan, fixed at start, and
    what is done.

    The plan is a turned black-dot design, the calibration the session is aimed through and
    the runs of each step, in order:

        run           at fps' landing depth and target, aimed through the prior, landing too
        fit           fps calibrateBlindMove operatingPoint on the runs
        validation    at the operating point, aimed through the new calibration, then fps
                      validateBlindMove

    Progress is the visits of each step and the calibration fitted, so a sequence that
    stopped can be continued from the first step not done.
    """

    STEPS = ('run', 'validation')

    def __init__(self, designId, priorCalibId, runConfig, seqKeys, nRuns=0, nValidationRuns=0,
                 nRetries=0, calibId=None):
        self.designId = designId
        self.priorCalibId = priorCalibId
        self.runConfig = dict(runConfig)
        self.seqKeys = dict(seqKeys)
        self.planned = dict(run=int(nRuns), validation=int(nValidationRuns))
        self.nRetries = int(nRetries)

        self.visits = {step: [] for step in self.STEPS}
        self.calibId = calibId
        self.validated = False

    def remaining(self, step):
        """Runs of `step` still to take."""
        return self.planned[step] - len(self.visits[step])

    def newValidation(self, nRuns):
        """Discard the validation runs so far: the next `nRuns` start a fresh validation."""
        self.planned['validation'] = int(nRuns)
        self.visits['validation'] = []
        self.validated = False

    def __str__(self):
        done = ', '.join(f'{step} {len(self.visits[step])}/{self.planned[step]}'
                         for step in self.STEPS if self.planned[step])
        calib = 'not fitted' if self.calibId is None else f'calibration {self.calibId}'
        aimed = '' if self.priorCalibId is None else f'aimed through {self.priorCalibId}: '
        return f'{aimed}{done}; {calib}, {"validated" if self.validated else "not validated"}'
