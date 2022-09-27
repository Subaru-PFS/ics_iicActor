from ics.iicActor.fps.sequence import FpsSequence


class MoveToPfsDesign(FpsSequence):
    """ fps MoveToPfsDesign command. """
    seqtype = 'moveToPfsDesign'
    timeLim = 900
    dependencies = ['mcs']

    def __init__(self, visitId, designId, exptime, maskFile, doTest=False, **kwargs):
        FpsSequence.__init__(self, **kwargs)
        # turning illuminators on
        self.add(actor='sps', cmdStr='bia on')
        self.add(actor='peb', cmdStr='led on')
        # move cobras to home, not supposed to, but meh.
        self.add(actor='fps', cmdStr='moveToHome all', visit=visitId, exptime=exptime, timeLim=300)
        # move to pfsDesign.
        self.add(actor='fps', cmdStr='moveToPfsDesign', visit=visitId, designId=designId, exptime=exptime,
                 maskFile=maskFile, timeLim=MoveToPfsDesign.timeLim)
        # turning illuminators off
        self.tail.add(actor='sps', cmdStr='bia off')
        self.tail.add(actor='peb', cmdStr='led off')


class MoveToHome(FpsSequence):
    """ fps MoveToHome command."""
    seqtype = 'moveToHome'
    timeLim = 900
    dependencies = ['mcs']

    def __init__(self, visitId, exptime, doTest=False, **kwargs):
        FpsSequence.__init__(self, **kwargs)
        # turning illuminators on
        self.add(actor='sps', cmdStr='bia on')
        self.add(actor='peb', cmdStr='led on')
        # move cobras to home, not supposed to, but meh.
        self.add(actor='fps', cmdStr='moveToHome all', visit=visitId, exptime=exptime, timeLim=300)
        # turning illuminators off
        self.tail.add(actor='sps', cmdStr='bia off')
        self.tail.add(actor='peb', cmdStr='led off')


class MovePhiToAngle(FpsSequence):
    """ fps MovePhiToAngle command. """
    seqtype = 'movePhiToAngle'
    timePerIteration = 150
    dependencies = ['mcs']

    def __init__(self, angle, iteration, doTest=False, **kwargs):
        FpsSequence.__init__(self, **kwargs)
        timeLim = iteration * MovePhiToAngle.timePerIteration
        self.fpsCommand(angle=angle, iteration=iteration, timeLim=timeLim)


class MoveToSafePosition(FpsSequence):
    """ fps MoveToSafePosition command. """
    seqtype = 'moveToSafePosition'
    timeLim = 900
    dependencies = ['mcs']

    def __init__(self, doTest=False, **kwargs):
        FpsSequence.__init__(self, **kwargs)
        self.fpsCommand(timeLim=MoveToSafePosition.timeLim)


class GotoVerticalFromPhi60(FpsSequence):
    """ fps GotoVerticalFromPhi60 command. """
    seqtype = 'gotoVerticalFromPhi60'
    timeLim = 900
    dependencies = ['mcs']

    def __init__(self, doTest=False, **kwargs):
        FpsSequence.__init__(self, **kwargs)
        self.fpsCommand(timeLim=GotoVerticalFromPhi60.timeLim)


class MakeMotorMap(FpsSequence):
    """ fps MakeMotorMap command. """
    seqtype = 'makeMotorMap'
    timePerRepeat = 150
    dependencies = ['mcs']

    def __init__(self, phi, theta, stepsize, repeat, slowOnly, doTest=False, **kwargs):
        FpsSequence.__init__(self, **kwargs)
        timeLim = repeat * MakeMotorMap.timePerRepeat
        self.fpsCommand(phi=phi, theta=theta, stepsize=stepsize, repeat=repeat, slowOnly=slowOnly, timeLim=timeLim)


class MakeOntimeMap(FpsSequence):
    """ fps MakeOntimeMap command. """
    seqtype = 'makeOntimeMap'
    timeLim = 900
    dependencies = ['mcs']

    def __init__(self, phi, theta, doTest=False, **kwargs):
        FpsSequence.__init__(self, **kwargs)
        self.fpsCommand(phi=phi, theta=theta, timeLim=MakeOntimeMap.timeLim)


class AngleConvergenceTest(FpsSequence):
    """ fps AngleConvergenceTest command. """
    seqtype = 'angleConvergenceTest'
    timeLim = 900
    dependencies = ['mcs']

    def __init__(self, phi, theta, angleTargets, doTest=False, **kwargs):
        FpsSequence.__init__(self, **kwargs)
        self.fpsCommand(phi=phi, theta=theta, angleTargets=angleTargets, timeLim=AngleConvergenceTest.timeLim)


class TargetConvergenceTest(FpsSequence):
    """ fps TargetConvergenceTest command. """
    seqtype = 'targetConvergenceTest'
    timeLim = 900
    dependencies = ['mcs']

    def __init__(self, ontime, speed, totalTargets, maxsteps, doTest=False, **kwargs):
        FpsSequence.__init__(self, **kwargs)
        timeLim = int(TargetConvergenceTest.timeLim / speed)
        self.fpsCommand(ontime=ontime, speed=speed, totalTargets=totalTargets, maxsteps=maxsteps, timeLim=timeLim)


class MotorOntimeSearch(FpsSequence):
    """ fps MotorOntimeSearch command. """
    seqtype = 'motorOntimeSearch'
    timeLim = 900
    dependencies = ['mcs']

    def __init__(self, phi, theta, doTest=False, **kwargs):
        FpsSequence.__init__(self, **kwargs)
        self.fpsCommand(phi=phi, theta=theta, timeLim=MotorOntimeSearch.timeLim)
