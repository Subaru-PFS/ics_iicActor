from importlib import reload

import ics.iicActor.sequenceList.fps as fpsSequence
import ics.iicActor.utils.lib as iicUtils
import ics.iicActor.utils.translate as translate
import ics.utils.cmd as cmdUtils
import iicActor.utils.pfsDesign.opdb as designDB
import numpy as np
import opscore.protocols.keys as keys
import opscore.protocols.types as types
import pandas as pd
from ics.utils.threading import singleShot
from iicActor.utils.engine import ExecMode
from pfs.datamodel.pfsConfig import TargetType

reload(fpsSequence)
reload(iicUtils)
reload(designDB)


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
        self.vocab = [
            ('startBoresightAcquisition', '[<expTime>] [<nExposures>]', self.startBoresightAcquisition),
            ('addBoresightPosition', '', self.addBoresightPosition),
            ('reduceBoresightData', '', self.reduceBoresightData),
            ('abortBoresightAcquisition', '', self.abortBoresightAcquisition),
            ('fpsLoop', '[<expTime>] [<cnt>]', self.fpsLoop),

            ('moveToPfsDesign',
             f'[<designId>] [<exptime>] [<maskFile>] [@(noHome)] [@(twoStepsOff)] [@(noTweak)] [<nIteration>] [<tolerance>] [@shortExpOff] {translate.seqArgs}',
             self.moveToPfsDesign),
            ('moveToHome', f'[@(all)] [<exptime>] [<designId>] [<maskFile>] [<wrtMaskFile>] {translate.seqArgs}',
             self.moveToHome),
            ('genPfsConfigFromMcs', f'[<designId>] {translate.seqArgs}', self.genPfsConfigFromMcs),
            ('cobraMoveAngles', '@(phi|theta) <angle> [@(genPfsConfig)] [<maskFile>]', self.cobraMoveAngles),
            ('cobraMoveSteps', '@(phi|theta) <stepsize> [@(genPfsConfig)] [<maskFile>]', self.cobraMoveSteps),
            # from here not really used.

            ('movePhiToAngle', f'<angle> <nIteration> {translate.seqArgs}', self.movePhiToAngle),
            ('moveToSafePosition', f'{translate.seqArgs}', self.moveToSafePosition),
            ('gotoVerticalFromPhi60', f'{translate.seqArgs}', self.gotoVerticalFromPhi60),
            ('makeMotorMap', f'@(phi|theta) <stepsize> <repeat> [@slowOnly] {translate.seqArgs}', self.makeMotorMap),
            ('makeOntimeMap', f'@(phi|theta) {translate.seqArgs}', self.makeOntimeMap),
            ('angleConvergenceTest', f'@(phi|theta) <angleTargets> {translate.seqArgs}', self.angleConvergenceTest),
            ('targetConvergenceTest', f'@(ontime|speed) <totalTargets> <maxsteps> {translate.seqArgs}',
             self.targetConvergenceTest),
            ('motorOntimeSearch', f'@(phi|theta) {translate.seqArgs}', self.motorOntimeSearch),

        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("iic_fps", (1, 1),
                                        keys.Key('name', types.String(), help='iic_sequence name'),
                                        keys.Key('comments', types.String(), help='iic_sequence comments'),
                                        keys.Key('groupId', types.Int(), help='optional groupId'),
                                        keys.Key('head', types.String() * (1,), help='cmdStr list to process before'),
                                        keys.Key('tail', types.String() * (1,), help='cmdStr list to process after'),

                                        keys.Key("nPositions", types.Int(),
                                                 help="number of angles to measure at"),
                                        keys.Key("nExposures", types.Int(),
                                                 help="number of exposures to take at each position"),
                                        keys.Key('exptime', types.Float() * (1,), help='exptime list (seconds)'),

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
                                        keys.Key("nIteration", types.Int(), help="Interation number"),
                                        keys.Key("tolerance", types.Float(), help="Tolerance distance in mm"),
                                        keys.Key("designId", types.Long(),
                                                 help="pfsDesignId for the field,which defines the fiber positions"),
                                        keys.Key('maskFile', types.String() * (1,),
                                                 help='filename containing which fibers to expose.'),
                                        keys.Key('wrtMaskFile', types.String() * (1,),
                                                 help='move with respect to that maskFile.'),
                                        )

    @property
    def engine(self):
        return self.actor.engine

    @property
    def visitManager(self):
        return self.engine.visitManager

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
        if self.boresightLoop is not None:
            cmd.fail('text="there is already a loop running"')
            return

        self.boresightLoop = fpsSequence.BoresightLoop.fromCmdKeys(self.actor, cmd.cmd.keywords)
        # doing startup manually, that will get a visit.
        self.engine.run(cmd, self.boresightLoop, mode=ExecMode.CHECKIN)

    @singleShot
    def addBoresightPosition(self, cmd):
        """
        `iic addBoresightPosition`

        Acquire data for a new boresight position.
        """
        if self.boresightLoop is None:
            cmd.fail('text="no boresight loop to add to"')
            return

        # setting sequence status back to ready, hard amend because flexibility.
        self.boresightLoop.setCmd(cmd)
        self.boresightLoop.status.hardAmend()

        # add position and run.
        self.boresightLoop.addPosition()
        self.engine.run(cmd, self.boresightLoop, mode=ExecMode.EXECUTE)

    @singleShot
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

        if nFrames < 2:
            cmd.fail('text="not enough frames to reduce')
            return

        # setting sequence status back to ready, hard amend because flexibility.
        self.boresightLoop.setCmd(cmd)
        self.boresightLoop.status.hardAmend()

        # adding calculateBoresight command.
        self.boresightLoop.addReduce(startFrame, endFrame)
        self.engine.run(cmd, self.boresightLoop, mode=ExecMode.EXECUTE | ExecMode.CONCLUDE)

        # no further reference to the object.
        self.boresightLoop = None

    def abortBoresightAcquisition(self, cmd):
        """
        `iic abortBoresightAcquisition`

        Abort a boresight acquisition loop.
        """
        if self.boresightLoop is None:
            cmd.fail('text="no boresight loop to abort"')
            return

        self.boresightLoop.setCmd(cmd)
        self.boresightLoop.doAbort(cmd)
        self.boresightLoop.finalize()

        # no further reference to the object.
        self.boresightLoop = None
        cmd.finish('text="boresight loop aborted"')

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

        FpsLoop = fpsSequence.FpsLoop.fromCmdKeys(self.actor, cmdKeys)
        self.engine.runInThread(cmd, FpsLoop)

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

        # then declare new design.
        if 'designId' in cmdKeys:
            self.actor.declareFpsDesign(cmd)

        designId = self.visitManager.getCurrentDesignId()

        moveToDesign = fpsSequence.MoveToPfsDesign.fromCmdKeys(self.actor, cmdKeys, designId=designId)
        self.engine.runInThread(cmd, moveToDesign)

    @singleShot
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

        maskFileArgs = translate.getMaskFileArgsFromCmd(cmdKeys, self.actor.actorConfig)

        cmdVar = self.actor.cmdr.call(actor='fps', cmdStr=f'createHomeDesign {maskFileArgs}'.strip(), timeLim=10)
        keys = cmdUtils.cmdVarToKeys(cmdVar)
        designId = int(keys['fpsDesignId'].values[0], 16)

        self.actor.declareFpsDesign(cmd, designId=designId)
        activePfsDesign = self.actor.engine.visitManager.activeField.pfsDesign
        toBeMoved = activePfsDesign.targetType == TargetType.HOME

        # updating targetType for fibers that were already revealed
        if 'wrtMaskFile' in cmdKeys:
            wrtMaskFile = pd.read_csv(translate.constructMaskFilePath(cmdKeys["wrtMaskFile"].values[0],
                                                                      self.actor.actorConfig), index_col=0)
            alreadyMoved = np.isin(activePfsDesign.fiberId, wrtMaskFile.fiberId[wrtMaskFile.bitMask == 1])
            activePfsDesign.targetType[np.logical_and(alreadyMoved, toBeMoved)] = TargetType.UNASSIGNED
            # writing updated design.
            activePfsDesign.write(self.actor.actorConfig['pfsDesign']['rootDir'])

        moveToHome = fpsSequence.MoveToHome.fromCmdKeys(self.actor, cmdKeys, designId=designId)
        self.engine.run(cmd, moveToHome, doFinish=False)

        if 'wrtMaskFile' in cmdKeys:
            # rewriting designFile back to original values.
            activePfsDesign.targetType[toBeMoved] = TargetType.HOME
            activePfsDesign.write(self.actor.actorConfig['pfsDesign']['rootDir'])
            # also updating pfsConfig0.
            if self.actor.engine.visitManager.activeField.pfsConfig0:
                self.actor.engine.visitManager.activeField.pfsConfig0.targetType[toBeMoved] = TargetType.HOME

        if cmd.isAlive():
            cmd.finish()

    def genPfsConfigFromMcs(self, cmd):
        """"""
        cmdKeys = cmd.cmd.keywords

        # then declare new design.
        if 'designId' in cmdKeys:
            self.actor.declareFpsDesign(cmd)

        designId = self.visitManager.getCurrentDesignId()

        genPfsConfigFromMcs = fpsSequence.GenPfsConfigFromMcs.fromCmdKeys(self.actor, cmdKeys, designId=designId)
        self.engine.runInThread(cmd, genPfsConfigFromMcs)

    def cobraMoveAngles(self, cmd):
        """
        `iic cobraMoveAngles angle=N [name=\"SSS\"] [comments=\"SSS\"]`

        Move Theta/Phi arm to angle.

        Parameters
        ---------
        angle : `int`
           specified angle .
        name : `str`
           To be inserted in opdb:iic_sequence.name.
        comments : `str`
           To be inserted in opdb:iic_sequence.comments.
        """
        cmdKeys = cmd.cmd.keywords

        designId = self.visitManager.getCurrentDesignId()

        cobraMoveAngles = fpsSequence.CobraMoveAngles.fromCmdKeys(self.actor, cmdKeys, designId=designId)
        self.engine.runInThread(cmd, cobraMoveAngles)

    def cobraMoveSteps(self, cmd):
        """
        `iic cobraMoveSteps stepsize=N [name=\"SSS\"] [comments=\"SSS\"]`

        Move Theta/Phi arm to stepsize.

        Parameters
        ---------
        stepsize : `int`
           specified step size .
        name : `str`
           To be inserted in opdb:iic_sequence.name.
        comments : `str`
           To be inserted in opdb:iic_sequence.comments.
        """
        cmdKeys = cmd.cmd.keywords

        designId = self.visitManager.getCurrentDesignId()

        cobraMoveSteps = fpsSequence.CobraMoveSteps.fromCmdKeys(self.actor, cmdKeys, designId=designId)
        self.engine.runInThread(cmd, cobraMoveSteps)

    def movePhiToAngle(self, cmd):
        """
        `iic movePhiToAngle angle=N nIteration=N [name=\"SSS\"] [comments=\"SSS\"]`

        Move Phi arm to angle.

        Parameters
        ---------
        angle : `int`
           specified angle .
        nIteration : `int`
           Number of iteration.
        name : `str`
           To be inserted in opdb:iic_sequence.name.
        comments : `str`
           To be inserted in opdb:iic_sequence.comments.
        """
        cmdKeys = cmd.cmd.keywords

        movePhiToAngle = fpsSequence.MovePhiToAngle.fromCmdKeys(self.actor, cmdKeys)
        self.engine.runInThread(cmd, movePhiToAngle)

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
        cmdKeys = cmd.cmd.keywords

        moveToSafePosition = fpsSequence.MoveToSafePosition.fromCmdKeys(self.actor, cmdKeys)
        self.engine.runInThread(cmd, moveToSafePosition)

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
        cmdKeys = cmd.cmd.keywords

        gotoVerticalFromPhi60 = fpsSequence.GotoVerticalFromPhi60.fromCmdKeys(self.actor, cmdKeys)
        self.engine.runInThread(cmd, gotoVerticalFromPhi60)

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

        makeMotorMap = fpsSequence.MakeMotorMap.fromCmdKeys(self.actor, cmdKeys)
        self.engine.runInThread(cmd, makeMotorMap)

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

        makeOntimeMap = fpsSequence.MakeOntimeMap.fromCmdKeys(self.actor, cmdKeys)
        self.engine.runInThread(cmd, makeOntimeMap)

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

        angleConvergenceTest = fpsSequence.AngleConvergenceTest.fromCmdKeys(self.actor, cmdKeys)
        self.engine.runInThread(cmd, angleConvergenceTest)

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

        targetConvergenceTest = fpsSequence.TargetConvergenceTest.fromCmdKeys(self.actor, cmdKeys)
        self.engine.runInThread(cmd, targetConvergenceTest)

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

        motorOnTimeSearch = fpsSequence.MotorOnTimeSearch.fromCmdKeys(self.actor, cmdKeys)
        self.engine.runInThread(cmd, motorOnTimeSearch)
