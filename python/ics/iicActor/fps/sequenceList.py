from ics.iicActor.fps.sequence import FpsSequence


class MoveToPfsDesign(FpsSequence):
    """ fps MoveToPfsDesign command. """
    seqtype = 'moveToPfsDesign'
    timeLim = 900
    dependencies = ['mcs']

    def __init__(self, pfsDesign, doTest=False, **kwargs):
        FpsSequence.__init__(self, **kwargs)
        self.fpsCommand(pfsDesign=pfsDesign)


class MovePhiToAngle(FpsSequence):
    """ fps MovePhiToAngle command. """
    seqtype = 'movePhiToAngle'
    timeLim = 900
    dependencies = ['mcs']

    def __init__(self, angle, iteration, doTest=False, **kwargs):
        FpsSequence.__init__(self, **kwargs)
        self.fpsCommand(angle=angle, iteration=iteration)


class MoveToHome(FpsSequence):
    """ fps MoveToHome command."""
    seqtype = 'moveToHome'
    timeLim = 900
    dependencies = ['mcs']

    def __init__(self, phi, theta, all, doTest=False, **kwargs):
        FpsSequence.__init__(self, **kwargs)
        self.fpsCommand(phi=phi, theta=theta, all=all)


class MoveToSafePosition(FpsSequence):
    """ fps MoveToSafePosition command. """
    seqtype = 'moveToSafePosition'
    timeLim = 900
    dependencies = ['mcs']

    def __init__(self, doTest=False, **kwargs):
        FpsSequence.__init__(self, **kwargs)
        self.fpsCommand()


class GotoVerticalFromPhi60(FpsSequence):
    """ fps GotoVerticalFromPhi60 command. """
    seqtype = 'gotoVerticalFromPhi60'
    timeLim = 900
    dependencies = ['mcs']

    def __init__(self, doTest=False, **kwargs):
        FpsSequence.__init__(self, **kwargs)
        self.fpsCommand()


class MakeMotorMap(FpsSequence):
    """ fps MakeMotorMap command. """
    seqtype = 'makeMotorMap'
    timeLim = 900
    dependencies = ['mcs']

    def __init__(self, phi, theta, stepsize, repeat, slowOnly, doTest=False, **kwargs):
        FpsSequence.__init__(self, **kwargs)
        self.fpsCommand(phi=phi, theta=theta, stepsize=stepsize, repeat=repeat, slowOnly=slowOnly)


class MakeOntimeMap(FpsSequence):
    """ fps MakeOntimeMap command. """
    seqtype = 'makeOntimeMap'
    timeLim = 900
    dependencies = ['mcs']

    def __init__(self, phi, theta, doTest=False, **kwargs):
        FpsSequence.__init__(self, **kwargs)
        self.fpsCommand(phi=phi, theta=theta)


class AngleConvergenceTest(FpsSequence):
    """ fps AngleConvergenceTest command. """
    seqtype = 'angleConvergenceTest'
    timeLim = 900
    dependencies = ['mcs']

    def __init__(self, phi, theta, angleTargets, doTest=False, **kwargs):
        FpsSequence.__init__(self, **kwargs)
        self.fpsCommand(phi=phi, theta=theta, angleTargets=angleTargets)


class TargetConvergenceTest(FpsSequence):
    """ fps TargetConvergenceTest command. """
    seqtype = 'targetConvergenceTest'
    timeLim = 900
    dependencies = ['mcs']

    def __init__(self, ontime, speed, totalTargets, maxsteps, doTest=False, **kwargs):
        FpsSequence.__init__(self, **kwargs)
        self.fpsCommand(ontime=ontime, speed=speed, totalTargets=totalTargets, maxsteps=maxsteps)


class MotorOntimeSearch(FpsSequence):
    """ fps MotorOntimeSearch command. """
    seqtype = 'motorOntimeSearch'
    timeLim = 900
    dependencies = ['mcs']

    def __init__(self, phi, theta, doTest=False, **kwargs):
        FpsSequence.__init__(self, **kwargs)
        self.fpsCommand(phi=phi, theta=theta, )
