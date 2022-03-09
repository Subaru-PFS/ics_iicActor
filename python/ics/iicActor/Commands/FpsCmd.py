from importlib import reload

import ics.iicActor.fps.sequenceList as fpsSequence
import ics.iicActor.utils.lib as iicUtils
import opscore.protocols.keys as keys
import opscore.protocols.types as types
from ics.utils import visit

reload(fpsSequence)
reload(iicUtils)


class BoresightLoop(object):
    """The state required to run a boresight measurement loop.

    Basically, the Gen2 command knows about the telescope motion, and
    interleaves POPT2 rotations with requests to us to expose. At the
    end we are commanded to read the data and generate a new boresight.

    """

    def __init__(self, visit, expTime, nExposures):
        self.visit = visit
        self.expTime = expTime
        self.nExposures = nExposures

    @property
    def startFrame(self):
        return self.visit.visitId * 100

    @property
    def endFrame(self):
        return self.visit.visitId * 100 + self.visit.fpsFrameId() - 1

    def nextFrameId(self):
        return self.visit.frameForFPS()


class FpsCmd(object):

    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        self.boresightLoop = None

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        seqArgs = '[<name>] [<comments>]'
        self.vocab = [
            ('startBoresightAcquisition', '[<expTime>] [<nExposures>]',
             self.startBoresightAcquisition),
            ('addBoresightPosition', '', self.addBoresightPosition),
            ('reduceBoresightData', '', self.reduceBoresightData),
            ('abortBoresightAcquisition', '', self.abortBoresightAcquisition),
            ('fpsLoop', '[<expTime>] [<cnt>]', self.fpsLoop),
            # ('mcsLoop', '[<expTime>] [<cnt>] [@noCentroids]', self.mcsLoop),

            ('moveToPfsDesign', f'<designId> {seqArgs}', self.moveToPfsDesign),
            ('movePhiToAngle', f'<angle> <iteration> {seqArgs}', self.movePhiToAngle),
            ('moveToHome', f'@(phi|theta|all) {seqArgs}', self.moveToHome),
            ('moveToSafePosition', f'{seqArgs}', self.moveToSafePosition),
            ('gotoVerticalFromPhi60', f'{seqArgs}', self.gotoVerticalFromPhi60),
            ('makeMotorMap', f'@(phi|theta) <stepsize> <repeat> [@slowOnly] {seqArgs}', self.makeMotorMap),
            ('makeOntimeMap', f'@(phi|theta) {seqArgs}', self.makeOntimeMap),
            ('angleConvergenceTest', f'@(phi|theta) <angleTargets> {seqArgs}', self.angleConvergenceTest),
            ('targetConvergenceTest', f'@(ontime|speed) <totalTargets> <maxsteps> {seqArgs}',
             self.targetConvergenceTest),
            ('motorOntimeSearch', f'@(phi|theta) {seqArgs}', self.motorOntimeSearch),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("iic_iic", (1, 1),
                                        keys.Key("nPositions", types.Int(),
                                                 help="number of angles to measure at"),
                                        keys.Key("nExposures", types.Int(),
                                                 help="number of exposures to take at each position"),
                                        keys.Key("expTime", types.Float(),
                                                 default=1.0,
                                                 help="Seconds for exposure"),
                                        keys.Key('name', types.String(), help='sps_sequence name'),
                                        keys.Key('comments', types.String(), help='sps_sequence comments'),
                                        keys.Key("cnt", types.Int(), default=1, help="times to run loop"),
                                        keys.Key("angle", types.Int(), help="arm angle"),
                                        keys.Key("stepsize", types.Int(), help="step size of motor"),
                                        keys.Key("repeat", types.Int(),
                                                 help="number of iteration for motor map generation"),
                                        keys.Key("angleTargets", types.Int(),
                                                 help="Target number for angle convergence"),
                                        keys.Key("totalTargets", types.Int(),
                                                 help="Target number for 2D convergence"),
                                        keys.Key("maxsteps", types.Int(),
                                                 help="Maximum step number for 2D convergence test"),
                                        keys.Key("iteration", types.Int(), help="Interation number"),
                                        keys.Key("designId", types.Long(),
                                                 help="pfsDesignId for the field,which defines the fiber positions"),
                                        )

    @property
    def resourceManager(self):
        return self.actor.resourceManager

    def moveToPfsDesign(self, cmd):
        """
        `iic moveToPfsDesign designId=??? [name=\"SSS\"] [comments=\"SSS\"]`

        Move cobras to provided pfsDesignId.

        Parameters
        ---------
        designId : `int`
           specified designId .
        name : `str`
           To be inserted in opdb:iic_sequence.name.
        comments : `str`
           To be inserted in opdb:iic_sequence.comments.
        """
        cmdKeys = cmd.cmd.keywords

        seqKwargs = iicUtils.genSequenceKwargs(cmd)
        designId = cmdKeys['designId'].values[0]
        cmd.inform('designId=0x%016x' % designId)

        job = self.resourceManager.request(cmd, fpsSequence.MoveToPfsDesign)
        job.instantiate(cmd, designId=designId, **seqKwargs)

        job.fire(cmd)

    def movePhiToAngle(self, cmd):
        """
        `iic movePhiToAngle angle=N iteration=N [name=\"SSS\"] [comments=\"SSS\"]`

        Move Phi arm to angle.

        Parameters
        ---------
        angle : `int`
           specified angle .
        iteration : `int`
           Number of iteration.
        name : `str`
           To be inserted in opdb:iic_sequence.name.
        comments : `str`
           To be inserted in opdb:iic_sequence.comments.
        """
        cmdKeys = cmd.cmd.keywords

        seqKwargs = iicUtils.genSequenceKwargs(cmd)
        angle = cmdKeys['angle'].values[0]
        iteration = cmdKeys['iteration'].values[0]

        job = self.resourceManager.request(cmd, fpsSequence.MovePhiToAngle)
        job.instantiate(cmd, angle=angle, iteration=iteration, **seqKwargs)

        job.fire(cmd)

    def moveToHome(self, cmd):
        """
        `iic moveToHome phi|theta|all [name=\"SSS\"] [comments=\"SSS\"]`

        Move cobras (phi or theta or all) to home.

        Parameters
        ---------
        name : `str`
           To be inserted in opdb:iic_sequence.name.
        comments : `str`
           To be inserted in opdb:iic_sequence.comments.
        """
        cmdKeys = cmd.cmd.keywords

        seqKwargs = iicUtils.genSequenceKwargs(cmd)
        phi = 'phi' in cmdKeys
        theta = 'theta' in cmdKeys
        all = 'all' in cmdKeys

        job = self.resourceManager.request(cmd, fpsSequence.MoveToHome)
        job.instantiate(cmd, phi=phi, theta=theta, all=all, **seqKwargs)

        job.fire(cmd)

    def moveToSafePosition(self, cmd):
        """
        `iic moveToSafePosition [name=\"SSS\"] [comments=\"SSS\"]`

        Move cobras to safe position.

        Parameters
        ---------
        name : `str`
           To be inserted in opdb:iic_sequence.name.
        comments : `str`
           To be inserted in opdb:iic_sequence.comments.
        """
        seqKwargs = iicUtils.genSequenceKwargs(cmd)

        job = self.resourceManager.request(cmd, fpsSequence.MoveToSafePosition)
        job.instantiate(cmd, **seqKwargs)

        job.fire(cmd)

    def gotoVerticalFromPhi60(self, cmd):
        """
        `iic gotoVerticalFromPhi60 [name=\"SSS\"] [comments=\"SSS\"]`

        Go to vertical from phi 60deg.

        Parameters
        ---------
        name : `str`
           To be inserted in opdb:iic_sequence.name.
        comments : `str`
           To be inserted in opdb:iic_sequence.comments.
        """
        seqKwargs = iicUtils.genSequenceKwargs(cmd)
        job = self.resourceManager.request(cmd, fpsSequence.GotoVerticalFromPhi60)
        job.instantiate(cmd, **seqKwargs)

        job.fire(cmd)

    def makeMotorMap(self, cmd):
        """
        `iic makeMotorMap phi|theta stepsize=N repeat=N [@slowOnly] [name=\"SSS\"] [comments=\"SSS\"]`

        Make motorMap (phi or theta).

        Parameters
        ---------
        stepsize : `int`
           Step size.
        repeat : `int`
           Number of repeat.
        slowOnly : `bool`
           only slow mode.
        name : `str`
           To be inserted in opdb:iic_sequence.name.
        comments : `str`
           To be inserted in opdb:iic_sequence.comments.
        """
        cmdKeys = cmd.cmd.keywords

        seqKwargs = iicUtils.genSequenceKwargs(cmd)
        phi = 'phi' in cmdKeys
        theta = 'theta' in cmdKeys
        stepsize = cmdKeys['stepsize'].values[0]
        repeat = cmdKeys['repeat'].values[0]
        slowOnly = 'slowOnly' in cmdKeys

        job = self.resourceManager.request(cmd, fpsSequence.MakeMotorMap)
        job.instantiate(cmd, phi=phi, theta=theta, stepsize=stepsize, repeat=repeat, slowOnly=slowOnly, **seqKwargs)

        job.fire(cmd)

    def makeOntimeMap(self, cmd):
        """
        `iic makeOntimeMap phi|theta [name=\"SSS\"] [comments=\"SSS\"]`

        Make an on-time map (phi or theta).

        Parameters
        ---------
        name : `str`
           To be inserted in opdb:iic_sequence.name.
        comments : `str`
           To be inserted in opdb:iic_sequence.comments.
        """
        cmdKeys = cmd.cmd.keywords

        seqKwargs = iicUtils.genSequenceKwargs(cmd)
        phi = 'phi' in cmdKeys
        theta = 'theta' in cmdKeys

        job = self.resourceManager.request(cmd, fpsSequence.MakeOntimeMap)
        job.instantiate(cmd, phi=phi, theta=theta, **seqKwargs)

        job.fire(cmd)

    def angleConvergenceTest(self, cmd):
        """
        `iic angleConvergenceTest phi|theta angleTargets=N [name=\"SSS\"] [comments=\"SSS\"]`

        Perform an angle convergence test (phi or theta).

        Parameters
        ---------
        angleTargets : `int`
           angle targets.
        name : `str`
           To be inserted in opdb:iic_sequence.name.
        comments : `str`
           To be inserted in opdb:iic_sequence.comments.
        """
        cmdKeys = cmd.cmd.keywords

        seqKwargs = iicUtils.genSequenceKwargs(cmd)
        phi = 'phi' in cmdKeys
        theta = 'theta' in cmdKeys
        angleTargets = cmdKeys['angleTargets'].values[0]

        job = self.resourceManager.request(cmd, fpsSequence.AngleConvergenceTest)
        job.instantiate(cmd, phi=phi, theta=theta, angleTargets=angleTargets, **seqKwargs)

        job.fire(cmd)

    def targetConvergenceTest(self, cmd):
        """
        `iic targetConvergenceTest ontime|speed totalTargets=N maxsteps=N [name=\"SSS\"] [comments=\"SSS\"]`

        Perform a target convergence test (ontime or speed).

        Parameters
        ---------
        totalTargets : `int`
           Total targets.
        maxsteps : `int`
           Maximum number of steps.
        name : `str`
           To be inserted in opdb:iic_sequence.name.
        comments : `str`
           To be inserted in opdb:iic_sequence.comments."""
        cmdKeys = cmd.cmd.keywords

        seqKwargs = iicUtils.genSequenceKwargs(cmd)
        ontime = 'ontime' in cmdKeys
        speed = 'speed' in cmdKeys
        totalTargets = cmdKeys['totalTargets'].values[0]
        maxsteps = cmdKeys['maxsteps'].values[0]

        job = self.resourceManager.request(cmd, fpsSequence.TargetConvergenceTest)
        job.instantiate(cmd, ontime=ontime, speed=speed, totalTargets=totalTargets, maxsteps=maxsteps, **seqKwargs)

        job.fire(cmd)

    def motorOntimeSearch(self, cmd):
        """
        `iic motorOntimeSearch phi|theta [name=\"SSS\"] [comments=\"SSS\"]`

        Perform a motor on-time search sequence (phi or theta).

        Parameters
        ---------
        name : `str`
           To be inserted in opdb:iic_sequence.name.
        comments : `str`
           To be inserted in opdb:iic_sequence.comments.
        """
        cmdKeys = cmd.cmd.keywords

        seqKwargs = iicUtils.genSequenceKwargs(cmd)
        phi = 'phi' in cmdKeys
        theta = 'theta' in cmdKeys

        job = self.resourceManager.request(cmd, fpsSequence.MotorOntimeSearch)
        job.instantiate(cmd, phi=phi, theta=theta, **seqKwargs)

        job.fire(cmd)

    def fpsLoop(self, cmd):
        """
        `iic fpsLoop [expTime=FF.F] [cnt=N]`

        Run an MCS+FPS loop, without moving cobras.

        Parameters
        ---------
        expTime : `float`
            MCS Exposure time.
        cnt: `int`
            Number of FPS images."""

        cmdKeys = cmd.cmd.keywords
        expTime = cmdKeys['expTime'].values[0] \
            if 'expTime' in cmdKeys \
            else 1.0
        cnt = cmdKeys['cnt'].values[0] \
            if 'cnt' in cmdKeys \
            else 1

        if cnt > 100:
            cmd.fail('text="cannot request more than 100 FPS images at once"')
            return

        try:
            ourVisit = self.actor.visitor.getVisit('fps', 'fpsLoop')
        except visit.VisitActiveError:
            cmd.fail('text="IIC already has an active visit: %s"' % (self.actor.visitor.activeVisit))
            raise

        fpsVisit = ourVisit.visitId
        timeLim = 30 + (15 + expTime) * cnt
        cmd.inform(f'text="setting timeout for nexp={cnt} exptime={expTime} to {timeLim}"')
        try:
            ret = self.actor.cmdr.call(actor='fps',
                                       cmdStr=f'testLoop cnt={cnt} expTime={expTime:0.2f} visit={fpsVisit}',
                                       timeLim=timeLim)
            if ret.didFail:
                raise RuntimeError("FPS failed to run a testLoop!")
        finally:
            self.actor.visitor.releaseVisit(fpsVisit)

        cmd.finish()

    def startBoresightAcquisition(self, cmd):
        """
        `iic startBoresightAcquisition [expTime=FF.F] [nExposures=N]`

        Start a boresight acquisition loop.

        Parameters
        ---------
        expTime : `float`
            MCS Exposure time.
        nExposures: `int`
            Number of exposure.
        """

        cmdKeys = cmd.cmd.keywords
        expTime = cmdKeys['expTime'].values[0] \
            if 'expTime' in cmdKeys \
            else 2.0
        nExposures = cmdKeys['nExposures'].values[0] \
            if 'nExposures' in cmdKeys \
            else 2

        if self.boresightLoop is not None:
            cmd.fail('text="boresight loop already in progress"')
            return

        try:
            visit = self.actor.visitor.getVisit('fps', 'boresightLoop')
        except Exception as e:
            cmd.fail('text="failed to start boresight loop: %s"' % e)
            return

        self.boresightLoop = BoresightLoop(visit, expTime, nExposures)
        cmd.finish('text="Initialized boresight loop"')

    def addBoresightPosition(self, cmd):
        """
        `iic addBoresightPosition`

        Acquire data for a new boresight position.
        """

        if self.boresightLoop is None:
            cmd.fail('text="no boresight loop to add to"')
            return

        expTime = self.boresightLoop.expTime
        for i in range(self.boresightLoop.nExposures):
            try:
                frameId = self.boresightLoop.nextFrameId()
                cmd.inform('text="taking MCS exposure %d/%d"' % (i + 1, self.boresightLoop.nExposures))
                ret = self.actor.cmdr.call(actor='mcs',
                                           cmdStr=f'expose object expTime={expTime:0.2f} frameId={frameId} ',
                                           timeLim=30 + expTime)
                if ret.didFail:
                    raise RuntimeError("IIC failed to take a MCS exposure")
            except RuntimeError:
                cmd.fail('text="ICC failed to take an MCS exposure')
            except Exception as e:
                cmd.fail('text="ICC failed to take an MCS exposure: %s"' % (e))

        cmd.finish()

    def reduceBoresightData(self, cmd):
        """
        `iic reduceBoresightData`

        Close out the current boresight acquisition loop and process the data.
        """

        if self.boresightLoop is None:
            cmd.fail('text="no boresight loop to reduce"')
            return

        startFrame = self.boresightLoop.startFrame
        endFrame = self.boresightLoop.endFrame
        nFrames = endFrame - startFrame + 1

        try:
            if nFrames < 2:
                raise RuntimeError('not enough frames')

            cmd.inform('text="measuring MCS center from %d frames from %s"' % (nFrames, startFrame))
            ret = self.actor.cmdr.call(actor='fps',
                                       cmdStr=f'calculateBoresight startFrame={startFrame} endFrame={endFrame}',
                                       timeLim=30)
            if ret.didFail:
                raise RuntimeError("FPS failed to calculate a boresight")
        except RuntimeError as e:
            cmd.fail('text="failed to reduce boresight, closed loop: %s"' % (str(e)))
            return
        finally:
            self.actor.visitor.releaseVisit(self.boresightLoop.visit.visitId)
            self.boresightLoop = None

        cmd.finish('')

    def abortBoresightAcquisition(self, cmd):
        """
        `iic abortBoresightAcquisition`

        Abort a boresight acquisition loop.
        """

        if self.boresightLoop is None:
            cmd.fail('text="no boresight loop to abort"')
            return

        self.actor.visitor.releaseVisit(self.boresightLoop.visit.visitId)
        self.boresightLoop = None

        cmd.finish('text="boresight loop aborted"')
