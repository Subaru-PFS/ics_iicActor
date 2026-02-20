from importlib import reload

import ics.iicActor.sequenceList.fps as fpsSequence
import ics.iicActor.utils.lib as iicUtils
import ics.iicActor.utils.pfsDesign.opdb as designDB
import ics.iicActor.utils.translate as translate
import ics.utils.cmd as cmdUtils
import numpy as np
import opscore.protocols.keys as keys
import opscore.protocols.types as types
import pandas as pd
from ics.iicActor.utils.engine import ExecMode
from ics.iicActor.utils.sequenceStatus import Flag
from ics.utils.threading import singleShot
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
             f'[<designId>] [<exptime>] [<maskFile>] [@(noHome)] [@(twoStepsOff)] [@(noTweak)] [<nIteration>] '
             f'[<tolerance>] [@shortExpOff] {translate.seqArgs}',
             self.moveToPfsDesign),

            ('moveToHome',
             f'[@(phi|theta|all)] [<exptime>] [<designId>] [<maskFile>] [<wrtMaskFile>] [@noMCSexposure] '
             f'[@genPfsConfig] {translate.seqArgs}', self.moveToHome),

            ('genPfsConfigFromMcs', f'[<designId>] {translate.seqArgs}', self.genPfsConfigFromMcs),
            ('cobraMoveAngles', '@(phi|theta) <angle> [@(genPfsConfig)] [<maskFile>]', self.cobraMoveAngles),
            ('cobraMoveSteps', '@(phi|theta) <stepsize> [@(genPfsConfig)] [<maskFile>]', self.cobraMoveSteps),

            ('phiCrossing', f'[<stepSize>] [<count>] [<exptime>] [<designId>] {translate.seqArgs}', self.dotCrossing),
            ('thetaCrossing', f'[<stepSize>] [<count>] [<exptime>] [<designId>] {translate.seqArgs}', self.dotCrossing),
            ('nearDotConvergence',
             f'@(phi|theta) [<designId>] [<exptime>] [<maskFile>] [@(noHome)] {translate.seqArgs}',
             self.nearDotConvergenceCmd),
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
                                        keys.Key('count', types.Int(), help='nExposure'),
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
        genPfsConfig = not 'noMCSexposure' in cmdKeys or 'genPfsConfig' in cmdKeys
        if 'theta' in cmdKeys:
            homingType = 'theta'
        elif 'phi' in cmdKeys:
            homingType = 'phi'
        else:
            homingType = 'all'

        maskFileArgs = translate.getMaskFileArgsFromCmd(cmdKeys, self.actor.actorConfig)

        cmdVar = self.actor.cmdr.call(actor='fps', cmdStr=f'createHomeDesign {homingType} {maskFileArgs}'.strip(),
                                      timeLim=10)
        keys = cmdUtils.cmdVarToKeys(cmdVar)
        designId = int(keys['fpsDesignId'].values[0], 16)

        self.actor.declareFpsDesign(cmd, designId=designId, genVisit0=genPfsConfig)
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

    def nearDotConvergence(self, cmd, designName=None, doFinish=True):
        """"""
        cmdKeys = cmd.cmd.keywords

        designName = 'phiCrossing-2022-06-19' if 'phi' in cmdKeys else designName
        designName = 'thetaCrossing-2022-06-19' if 'theta' in cmdKeys else designName

        # get dotCrossing designId from opdb or use provided new one.
        if 'designId' in cmdKeys:
            designId = cmdKeys['designId'].values[0]
        else:
            designId = designDB.latestDesignIdMatchingName(designName)

        # declare/insert current design as nearDotDesign.
        self.actor.declareFpsDesign(cmd, designId=designId)

        # run nearDotConvergence.
        nearDotConvergence = fpsSequence.NearDotConvergence.fromCmdKeys(self.actor, cmdKeys, designId=designId)
        self.engine.run(cmd, nearDotConvergence, doFinish=doFinish)

        return nearDotConvergence

    @singleShot
    def dotCrossing(self, cmd):
        """"""
        cmdName = cmd.cmd.name

        # converge to near dot in the first place.
        nearDotConvergence = self.nearDotConvergence(cmd, designName=cmdName, doFinish=False)
        # something happened, convergence did not complete, we need to stop here.
        if nearDotConvergence.status.flag != Flag.FINISHED:
            if cmd.alive:
                cmd.fail('text="NearDotConvergence not completed, stopping here."')
            return

        # retrieving which crossing is required.
        DotCrossing = fpsSequence.PhiCrossing if cmdName == 'phiCrossing' else fpsSequence.ThetaCrossing

        # run dotCrossing.
        dotCrossing = DotCrossing.fromCmdKeys(self.actor, cmd.cmd.keywords)
        self.engine.run(cmd, dotCrossing)

    @singleShot
    def nearDotConvergenceCmd(self, cmd):
        """Needs a dedicated command function for threading."""
        return self.nearDotConvergence(cmd)
