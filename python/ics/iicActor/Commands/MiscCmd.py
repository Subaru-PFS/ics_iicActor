import threading
from importlib import reload

import ics.iicActor.sequenceList.fps as fpsSequenceList
import ics.iicActor.sequenceList.misc as miscSequenceList
import ics.iicActor.sequenceList.sps as spsSequenceList
import ics.iicActor.sps.sequence as spsSequence
import ics.iicActor.utils.lib as iicUtils
import ics.iicActor.utils.translate as translate
from ics.iicActor.utils.blindMoveCalibration import BlindMoveCalibration
import ics.utils.cmd as cmdUtils
import opscore.protocols.keys as keys
import opscore.protocols.types as types
from ics.iicActor.utils.sequenceStatus import Flag
from ics.utils.threading import singleShot
from opscore.utility.qstr import qstr

reload(iicUtils)

reload(miscSequenceList)


MIN_ITERATION_RUNS = 3
"""Runs an iteration of calibrateBlindMove needs: fps calibrates no cobra on fewer by default."""

PROVISIONAL_MIN_RUNS = 2
"""Usable runs a cobra needs in the fit of an iteration that only aims the next one."""


class MiscCmd(object):

    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor
        # The blind-move calibration of this session, see calibrateBlindMove, and the lock
        # one calibrateBlindMove command holds while it runs.
        self.blindMoveCalibration = None
        self.blindMoveLock = threading.Lock()

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        identArgs = '[<cam>] [<cams>] [<specNum>] [<specNums>] [<arm>] [<arms>]'
        commonArgs = f'{identArgs} [<duplicate>] {translate.seqArgs}'

        self.vocab = [
            ('fiberIdentification', f'[<fiberGroups>] {commonArgs}', self.fiberIdentification),
            ('dotRoach', f'[<exptime>] [<maskFile>] [@(hscLamps)] [<mode>] {identArgs} {translate.seqArgs}',
             self.dotRoach),
            ('thetaPhiScan', 'start', self.startNewThetaPhiScan),
            ('thetaPhiScan', f'takeNextTheta [<groupId>] [<thetaAngle>] [<exptime>] {identArgs} {translate.seqArgs}',
             self.takeNextThetaPhiScan),
            ('thetaPhiScan', f'takeNextPhi [<groupId>] [<phiAngle>] [<exptime>] {identArgs} {translate.seqArgs}',
             self.takeNextPhiThetaScan),
            ('declareHomeDesign', '[@skipGenVisit0]', self.declareHomeDesign),
            ('calibrateBlindMove', f'start [<nRuns>] [<nValidationRuns>] '
                                   f'[<dotThetaOffset>] [<maskFile>] {translate.seqArgs}',
             self.startBlindMoveCalibration),
            ('calibrateBlindMove', 'continue', self.continueBlindMoveCalibration),
            ('calibrateBlindMove', f'validate [<calibId>] [<nValidationRuns>] '
                                   f'[<dotThetaOffset>] [<maskFile>] {translate.seqArgs}',
             self.validateBlindMoveCalibration),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("iic_misc", (1, 1),
                                        keys.Key('exptime', types.Float() * (1,), help='exptime list (seconds)'),
                                        keys.Key('duplicate', types.Int(), help='exposure duplicate (1 is default)'),
                                        keys.Key("cam", types.String() * (1,),
                                                 help='list of camera to take exposure from'),
                                        keys.Key("cams", types.String() * (1,),
                                                 help='list of camera to take exposure from'),
                                        keys.Key('specNum', types.Int() * (1,),
                                                 help='spectrograph module(s) to take exposure from'),
                                        keys.Key('specNums', types.Int() * (1,),
                                                 help='spectrograph module(s) to take exposure from'),
                                        keys.Key("arm", types.String() * (1,),
                                                 help='arm to take exposure from'),
                                        keys.Key("arms", types.String() * (1,),
                                                 help='arm to take exposure from'),
                                        keys.Key('name', types.String(), help='iic_sequence name'),
                                        keys.Key('comments', types.String(), help='iic_sequence comments'),
                                        keys.Key('groupId', types.Int(), help='optional groupId'),
                                        keys.Key('head', types.String() * (1,), help='cmdStr list to process before'),
                                        keys.Key('tail', types.String() * (1,), help='cmdStr list to process after'),
                                        keys.Key('maskFile', types.String() * (1,),
                                                 help='filename containing which fibers to expose.'),
                                        keys.Key('designId', types.Long(), help='selected nearDot designId'),
                                        keys.Key('fiberGroups', types.Int() * (1,),
                                                 help='which fiberGroups to identify 2->31'),
                                        keys.Key('mode', types.String() * (1,), help='mode for dotRoach'),
                                        keys.Key("thetaAngle", types.Int(), units='deg',
                                                 help="Designed theta angle (deg)"),
                                        keys.Key("phiAngle", types.Int(), units='deg',
                                                 help="Designed phi angle (deg)"),
                                        keys.Key('nRuns', types.Int() * (1,),
                                                 help='runs of each iteration at the operating point, '
                                                      'the first at the motor map'),
                                        keys.Key('nValidationRuns', types.Int(), help='validation runs'),
                                        keys.Key('dotThetaOffset', types.Float(), units='deg',
                                                 help='turn of the black dots about the cobra centres'),
                                        keys.Key('calibId', types.Int(), help='blind-move calibration'),
                                        )

    @property
    def engine(self):
        return self.actor.engine

    def _runFpsCreateDesign(self, createDesignCmdStr):
        """Send createDesign command to fps actor and return the resulting designId."""
        cmdVar = self.actor.cmdr.call(actor='fps', cmdStr=createDesignCmdStr.strip(), timeLim=10)
        keys = cmdUtils.cmdVarToKeys(cmdVar)
        designId = int(keys['fpsDesignId'].values[0], 16)

        return designId

    def _callFps(self, cmd, cmdStr, timeLim, failCmd=True):
        """Send `cmdStr` to fps for `cmd`; the cmdVar, or None if it failed.

        The failure is reported on `cmd`, which is also failed with `failCmd`.
        """
        cmdVar = self.actor.cmdr.call(actor='fps', cmdStr=cmdStr, forUserCmd=cmd, timeLim=timeLim)
        if cmdVar.didFail:
            reason = qstr(f'fps {cmdStr} failed: {cmdUtils.interpretFailure(cmdVar)}')
            if failCmd:
                cmd.fail(f'text={reason}')
            else:
                cmd.warn(f'text={reason}')
            return None
        return cmdVar

    def _declareTurnedDotDesign(self, cmd, cmdKeys, config):
        """Have fps create the black-dot design with its dots turned into view, and declare it.

        Returns
        -------
        `int` or None
            The designId; None once `cmd` has been failed.
        """
        offset = float(config['dotThetaOffset'])
        maskFileArgs = translate.getMaskFileArgsFromCmd(cmdKeys, self.actor.actorConfig)
        cmdVar = self._callFps(cmd, f'createBlackDotDesign dotThetaOffset={offset:g} '
                                    f'designName=blindMove_turned{offset:g} {maskFileArgs}'.strip(), 10)
        if cmdVar is None:
            return None
        designId = int(cmdUtils.cmdVarToKeys(cmdVar)['fpsDesignId'].values[0], 16)
        self.actor.declareFpsDesign(cmd, designId=designId)
        return designId

    def _runBlindMove(self, cmd, calibration, *, calibId, aimLanding):
        """One blind-move run, retried up to calibration.nRetries times; its visit, or None.

        calibId aims the push, and with aimLanding the landing, of every calibrated cobra;
        None aims nothing.  The run lands at fps' convergence.dotLanding and pushes to its
        convergence.dotTarget.
        """
        illuminators = translate.illuminatorKeys(self.actor.actorConfig)
        for attempt in range(calibration.nRetries + 1):
            run = fpsSequenceList.BlindMoveRun(calibration.designId,
                                               dotCalib='none' if calibId is None else calibId,
                                               aimLanding=aimLanding and calibId is not None,
                                               **calibration.runConfig, **calibration.seqKeys, **illuminators)
            self.engine.run(cmd, run, doFinish=False, failCmd=False)
            if run.status.flag == Flag.FINISHED:
                return run.visit.visitId
            # Only a run that failed is taken again; one aborted or finished by the operator,
            # or refused its resources, stops the command.
            if run.status.flag != Flag.FAILED or not cmd.alive:
                return None
            if attempt < calibration.nRetries:
                cmd.warn('text="blind-move run not completed, retrying"')
        return None

    def _fitBlindMove(self, cmd, visits, aimedThrough=None, minRuns=None):
        """Have fps measure a calibration on `visits`, aimed through calibration `aimedThrough`
        if not None, with fps' minRuns unless given; its id, or None."""
        cmdStr = f'calibrateBlindMove visits={",".join(map(str, visits))} operatingPoint'
        if aimedThrough is not None:
            cmdStr += f' priorCalib={aimedThrough}'
        if minRuns is not None:
            cmdStr += f' minRuns={minRuns}'
        cmdVar = self._callFps(cmd, cmdStr, 300, failCmd=False)
        if cmdVar is None:
            return None
        replyKeys = cmdUtils.cmdVarToKeys(cmdVar)
        if 'blindMoveCalibId' not in replyKeys:
            cmd.warn('text="fps calibrateBlindMove did not report blindMoveCalibId; is fps up to date?"')
            return None
        return int(replyKeys['blindMoveCalibId'].values[0])

    def _advanceBlindMoveCalibration(self, cmd, calibration):
        """Do every step of `calibration` not done yet, in order, and finish or fail `cmd`."""

        def stop(why):
            if cmd.alive:
                cmd.fail(f'text="{why}; {calibration}. iic calibrateBlindMove continue resumes here."')

        def runs(visits, planned, calibId):
            """Take the runs not taken yet, aimed through calibId; whether they all completed."""
            while len(visits) < planned:
                visit = self._runBlindMove(cmd, calibration, calibId=calibId, aimLanding=True)
                if visit is None:
                    return False
                visits.append(visit)
            return True

        for i, planned in enumerate(calibration.planned):
            if not runs(calibration.visits[i], planned, calibration.aimedThrough(i)):
                return stop(f'iteration {i + 1} run not completed')
            last = i == len(calibration.planned) - 1
            if calibration.fitted[i] is None:
                calibration.fitted[i] = self._fitBlindMove(cmd, calibration.visits[i],
                                                           aimedThrough=calibration.aimedThrough(i),
                                                           minRuns=None if last else PROVISIONAL_MIN_RUNS)
                if calibration.fitted[i] is None:
                    return stop(f'fps calibrateBlindMove failed on iteration {i + 1}')
                use = 'the session\'s calibration' if last else f'aims iteration {i + 2}'
                cmd.inform(f'text="iteration {i + 1}: blind-move calibration {calibration.fitted[i]} '
                           f'measured on visits {calibration.visits[i]}, {use}"')

        if not runs(calibration.validationVisits, calibration.nValidationRuns, calibration.calibId):
            return stop('validation run not completed')

        visits = ','.join(map(str, calibration.validationVisits))
        if self._callFps(cmd, f'validateBlindMove calibId={calibration.calibId} visits={visits}', 120,
                         failCmd=False) is None:
            if cmd.alive:
                cmd.fail(f'text="calibration {calibration.calibId} not validated on visits '
                         f'{calibration.validationVisits}; iic calibrateBlindMove validate takes new '
                         f'validation runs"')
            return
        calibration.validated = True
        cmd.finish(f'text="blind-move calibration {calibration.calibId} validated, now the default; '
                   f'{calibration}"')

    def _newBlindMoveCalibration(self, cmd, withCalibration, calibId=None):
        """A BlindMoveCalibration planned from the config and `cmd`, on a freshly declared design."""
        cmdKeys = cmd.cmd.keywords
        config = translate.resolveCmdConfig(cmdKeys, self.actor.actorConfig, 'calibrateBlindMove')

        nRuns = []
        if withCalibration:
            nRuns = config.get('nRuns', [4, 5])
            nRuns = [int(nRuns)] if isinstance(nRuns, int) else [int(n) for n in nRuns]
            if len(nRuns) < 2 or min(nRuns) < MIN_ITERATION_RUNS:
                cmd.fail(f'text="calibrateBlindMove: nRuns={",".join(map(str, nRuns))}: at least two '
                         f'iterations of {MIN_ITERATION_RUNS} runs or more are needed, one at the motor '
                         f'map and one aimed through its fit"')
                return None

        designId = self._declareTurnedDotDesign(cmd, cmdKeys, config)
        if designId is None:
            return None

        runConfig = {key: config[key] for key in fpsSequenceList.BlindMoveRun.configKeys}
        # Every run of the session in one sequence group.
        seqKeys = translate.seqKeys(cmdKeys)
        if seqKeys.get('groupId') is None:
            seqKeys['groupId'] = self.engine.requestGroupId('calibrateBlindMove')
        return BlindMoveCalibration(designId, runConfig, seqKeys, nRuns=nRuns,
                                    nValidationRuns=config.get('nValidationRuns', 2),
                                    nRetries=config.get('nRetries', 0), calibId=calibId)

    def _blindMoveCommand(self, cmd, step):
        """Run `step(cmd)` holding the calibrateBlindMove lock, or refuse if another holds it."""
        if not self.blindMoveLock.acquire(blocking=False):
            cmd.fail('text="a calibrateBlindMove command is already running"')
            return
        try:
            step(cmd)
        finally:
            self.blindMoveLock.release()

    @singleShot
    def startBlindMoveCalibration(self, cmd):
        """Start an operating-point blind-move calibration, see `BlindMoveCalibration`.

        No calibration enters it: the first iteration runs at the motor map.  A calibration
        that fails validation stays in opdb but does not become the default.
        """
        self._blindMoveCommand(cmd, self._startBlindMoveCalibration)

    def _startBlindMoveCalibration(self, cmd):
        calibration = self._newBlindMoveCalibration(cmd, withCalibration=True)
        if calibration is None:
            return
        self.blindMoveCalibration = calibration
        self._advanceBlindMoveCalibration(cmd, calibration)

    @singleShot
    def continueBlindMoveCalibration(self, cmd):
        """Resume the blind-move calibration of this session from its first step not done."""
        self._blindMoveCommand(cmd, self._continueBlindMoveCalibration)

    def _continueBlindMoveCalibration(self, cmd):
        calibration = self.blindMoveCalibration
        if calibration is None:
            cmd.fail('text="no blind-move calibration to continue; iic calibrateBlindMove start"')
            return
        if calibration.validated:
            cmd.fail(f'text="nothing to continue: {calibration}"')
            return
        self.actor.declareFpsDesign(cmd, designId=calibration.designId)
        self._advanceBlindMoveCalibration(cmd, calibration)

    @singleShot
    def validateBlindMoveCalibration(self, cmd):
        """New validation runs for this session's calibration, or for calibId=N on a new design."""
        self._blindMoveCommand(cmd, self._validateBlindMoveCalibration)

    def _validateBlindMoveCalibration(self, cmd):
        cmdKeys = cmd.cmd.keywords
        if 'calibId' in cmdKeys:
            previous = self.blindMoveCalibration
            if previous is not None and not previous.validated:
                cmd.warn(f'text="replacing the unfinished blind-move calibration ({previous})"')
            calibration = self._newBlindMoveCalibration(cmd, withCalibration=False,
                                                        calibId=int(cmdKeys['calibId'].values[0]))
            if calibration is None:
                return
            self.blindMoveCalibration = calibration
        else:
            calibration = self.blindMoveCalibration
            if calibration is None or calibration.calibId is None:
                cmd.fail('text="no fitted blind-move calibration to validate; give calibId="')
                return
            if 'dotThetaOffset' in cmdKeys or 'maskFile' in cmdKeys:
                cmd.fail('text="the session design is fixed; give calibId= to validate on a new one"')
                return
            # The validation plan, from the session's unless given.
            nRuns = (cmdKeys['nValidationRuns'].values[0] if 'nValidationRuns' in cmdKeys
                     else calibration.nValidationRuns)
            calibration.newValidation(nRuns)
            self.actor.declareFpsDesign(cmd, designId=calibration.designId)
        self._advanceBlindMoveCalibration(cmd, calibration)

    def fiberIdentification(self, cmd):
        """"""
        fiberIdentification = miscSequenceList.FiberIdentification.fromCmdKeys(self.actor, cmd.cmd.keywords)
        self.engine.runInThread(cmd, fiberIdentification)

    def genBlackDotsConfig(self, cmd):
        """"""
        cmdKeys = cmd.cmd.keywords

        maskFileArgs = translate.getMaskFileArgsFromCmd(cmdKeys, self.actor.actorConfig)
        designId = self._runFpsCreateDesign(f'createBlackDotDesign {maskFileArgs}')

        self.actor.declareFpsDesign(cmd, designId=designId)

        genPfsConfigFromMcs = fpsSequenceList.GenBlackDotsConfig.fromCmdKeys(self.actor, cmdKeys, designId=designId)
        self.engine.run(cmd, genPfsConfigFromMcs)

    @singleShot
    def dotRoach(self, cmd):
        """"""
        cmdKeys = cmd.cmd.keywords

        # defining all the sequence first.
        phiCrossingDesignId = self.engine.opdb.latestDesignIdMatchingName('phiCrossing-2022-06-19')

        # exptime in cmdKeys means SPS exptime but the sequence interpret it as MCS exptime, so we have to patch it.
        mcsExptime = self.actor.actorConfig['mcs']['exptime']
        illuminators = self.actor.actorConfig['illuminators']
        nearDotConvergenceConfig = {**self.actor.actorConfig['nearDotConvergence'], 'noHome': True}

        nearDotConvergence = fpsSequenceList.NearDotConvergence(phiCrossingDesignId,
                                                                **nearDotConvergenceConfig, **illuminators)
        # use pfiLamps by default.
        roaching = miscSequenceList.DotRoach if 'hscLamps' in cmdKeys else miscSequenceList.DotRoachPfiLamps
        roachingInit = miscSequenceList.DotRoachInit if 'hscLamps' in cmdKeys else miscSequenceList.DotRoachInitPfiLamps
        # now roaching is split in two steps.
        dotRoachInit = roachingInit.fromCmdKeys(self.actor, cmd.cmd.keywords)
        dotRoach = roaching.fromCmdKeys(self.actor, cmd.cmd.keywords)

        # first declare design and going home.
        homeDesignId = self.declareHomeDesign(cmd, doFinish=False)
        moveToHomeAll = fpsSequenceList.MoveToHome(exptime=mcsExptime, designId=homeDesignId, all=True, **illuminators)
        self.engine.run(cmd, moveToHomeAll, doFinish=False)

        if moveToHomeAll.status.flag != Flag.FINISHED:
            if cmd.alive:
                cmd.fail('text="moveToHome not completed, stopping here."')
            return

        # running dotRoach init to take reference flux.
        self.engine.run(cmd, dotRoachInit, doFinish=False)

        if dotRoachInit.status.flag != Flag.FINISHED:
            if cmd.alive:
                cmd.fail('text="dotRoachInit not completed, stopping here."')
            return

        # now declare phiCrossing design and  converge to near dot.
        self.actor.declareFpsDesign(cmd, designId=phiCrossingDesignId)
        self.engine.run(cmd, nearDotConvergence, doFinish=False)

        # something happened, convergence did not complete, we need to stop here.
        if nearDotConvergence.status.flag != Flag.FINISHED:
            if cmd.alive:
                cmd.fail('text="NearDotConvergence not completed, stopping here."')
            return

        # now proceed to with the actual roaching sequence.
        self.engine.run(cmd, dotRoach, doFinish=False)

        if dotRoach.status.flag != Flag.FINISHED:
            if cmd.alive:
                cmd.fail('text="dotRoach not completed, stopping here."')
            return

        self.genBlackDotsConfig(cmd)

    def startNewThetaPhiScan(self, cmd):
        """"""
        cmdKeys = cmd.cmd.keywords
        doContinue = 'continue' in cmdKeys
        groupName = cmdKeys['groupName'].values[0] if 'groupName' in cmdKeys else 'thetaPhiThroughputScan'
        try:
            groupId = self.engine.requestGroupId(groupName, doContinue=doContinue)
        except Exception as e:
            cmd.fail(f'text="{str(e)}"')
            return

        cmd.finish(f'groupId={groupId},{qstr(groupName)}')

    @singleShot
    def takeNextThetaPhiScan(self, cmd):
        self._thetaPhiScan(cmd, constantAxis='theta')

    @singleShot
    def takeNextPhiThetaScan(self, cmd):
        self._thetaPhiScan(cmd, constantAxis='phi')

    def _thetaPhiScan(self, cmd, constantAxis):
        innerAxis = 'phi' if constantAxis == 'theta' else 'theta'

        def bailIfNotFinished(seq, label):
            if seq.status.flag == Flag.FINISHED:
                return True
            if cmd.alive:
                cmd.fail(f'text="{label} not completed (status={seq.status.flag}), stopping here."')
            return False

        cmdKeys = cmd.cmd.keywords
        constantAngleKey = f'{constantAxis}Angle'
        constantAngle = cmdKeys[constantAngleKey].values[0] if constantAngleKey in cmdKeys else None
        groupId = cmdKeys['groupId'].values[0] if 'groupId' in cmdKeys else None

        mcsExptime = self.actor.actorConfig['mcs']['exptime']
        illuminators = self.actor.actorConfig['illuminators']
        thetaPhiScanConfig = self.actor.actorConfig['thetaPhiScan']
        scienceTraceConfig = thetaPhiScanConfig['scienceTrace']
        moveToPfsDesignConfig = thetaPhiScanConfig['moveToPfsDesign']
        phiAngles = thetaPhiScanConfig['phiAngles']
        thetaAngles = thetaPhiScanConfig['thetaAngles']
        scanPhiHome = thetaPhiScanConfig['scanPhiHome']
        scanThetaHome = thetaPhiScanConfig['scanThetaHome']

        constantAngles = thetaAngles if constantAxis == 'theta' else phiAngles
        scanAngles  = phiAngles if constantAxis == 'theta' else thetaAngles
        scanInnerHome = scanPhiHome if constantAxis == 'theta' else scanThetaHome

        if scanInnerHome:
            scanAngles = [scanAngles[0], 0] + scanAngles[1:]

        def getRemainingAngles(groupId):
            if constantAxis == 'theta':
                scanned = self.engine.opdb.getScannedThetaFromThetaPhiScanId(groupId, phiAngles=scanAngles)
            else:
                scanned = self.engine.opdb.getScannedPhiFromThetaPhiScanId(groupId, thetaAngles=scanAngles)
            remaining = list(set(constantAngles) - set(scanned))
            remaining.sort()
            return remaining

        if groupId is None:
            groupId = self.engine.opdb.latestThetaPhiScanId()

        try:
            remainingAngles = getRemainingAngles(groupId)
            cmd.inform(f'text="thetaPhiScan groupId={groupId} remaining {constantAxis}Angles: '
                       f'{",".join(map(str, remainingAngles))}"')
        except Exception as e:
            cmd.warn(f'text="{str(e)}"')
            remainingAngles = None

        if constantAngle is None:
            if remainingAngles is None:
                cmd.fail(f'text="cannot determine remaining {constantAxis} angles for groupId={groupId}; '
                         f'pass {constantAxis}Angle=<deg> explicitly"')
                return
            elif len(remainingAngles) == 0:
                cmd.finish(f'text="thetaPhiScan groupId={groupId} already covers all configured {constantAxis} angles '
                           f'({",".join(map(str, constantAngles))}); no further scan needed"')
                return
            constantAngle = remainingAngles[0]

        cmd.inform(f'text="thetaPhiScan groupId={groupId} {constantAxis}Angle={constantAngle:d} deg START"')

        name = f'{constantAxis}_{constantAngle:03d}'
        lampsKeys = dict(halogen=int(translate.resolveExptime(cmdKeys, scienceTraceConfig)))
        __, duplicate = translate.spsExposureKeys(cmdKeys, doRaise=False)
        windowKeys = translate.windowKeys(cmdKeys, scienceTraceConfig)
        cams = spsSequence.SpsSequence.keysToCam(self.actor, cmdKeys, configDict=scienceTraceConfig['idDict'])

        homeDesignId = self.declareHomeDesign(cmd, doFinish=False)
        moveToHomeAll = fpsSequenceList.MoveToHome(exptime=mcsExptime, designId=homeDesignId, all=True, **illuminators)
        self.engine.run(cmd, moveToHomeAll, doFinish=False)
        if not bailIfNotFinished(moveToHomeAll, 'moveToHome'):
            return

        scienceTrace = spsSequenceList.calib.ScienceTrace(cams, lampsKeys, duplicate, windowKeys,
                                                          groupId=groupId,
                                                          name=name,
                                                          comments='cobraHome')
        self.engine.run(cmd, scienceTrace, doFinish=False)
        if not bailIfNotFinished(scienceTrace, 'cobraHome scienceTrace'):
            return

        for innerAngle in scanAngles:
            thetaAngle, phiAngle = (constantAngle, innerAngle) if constantAxis == 'theta' else (innerAngle, constantAngle)
            designName = iicUtils.thetaPhiScanDesignName(thetaAngle, phiAngle,
                                                         atHome=innerAxis if innerAngle == 0 else None)

            if innerAngle == 0:
                designId = self._runFpsCreateDesign(f'createHomeDesign {innerAxis} designName={designName}')
                moveCobra = fpsSequenceList.MoveToHome(designId=designId, exptime=mcsExptime,
                                                       **{innerAxis: True}, **illuminators)
            else:
                designId = self._runFpsCreateDesign(
                    f'createThetaPhiScanDesign thetaAngle={thetaAngle:d} phiAngle={phiAngle:d} designName={designName}')
                moveCobra = fpsSequenceList.MoveToPfsDesign(designId=designId, **moveToPfsDesignConfig, **illuminators)

            self.actor.declareFpsDesign(cmd, designId=designId)
            self.engine.run(cmd, moveCobra, doFinish=False)
            if not bailIfNotFinished(moveCobra, f'cobra move to {designName}'):
                return

            scienceTrace = spsSequenceList.calib.ScienceTrace(cams, lampsKeys, duplicate, windowKeys,
                                                              name=name,
                                                              comments=designName,
                                                              groupId=groupId)
            self.engine.run(cmd, scienceTrace, doFinish=False)
            if not bailIfNotFinished(scienceTrace, f'{designName} scienceTrace'):
                return
            cmd.inform(f'text="thetaPhiScan groupId={groupId} {constantAxis}Angle={constantAngle:d} deg '
                       f'{innerAxis}Angle={innerAngle:d} deg DONE"')

        cmd.inform(f'text="thetaPhiScan groupId={groupId} {constantAxis}Angle={constantAngle:d} deg FINISHED"')
        remainingAngles = getRemainingAngles(groupId)
        cmd.inform(f'text="thetaPhiScan groupId={groupId} remaining {constantAxis}Angles: '
                   f'{",".join(map(str, remainingAngles))}"')
        cmd.finish(f'nRemaining{constantAxis.capitalize()}s={len(remainingAngles)}')

    def declareHomeDesign(self, cmd, doFinish=True, genVisit0=True):
        """Create a fresh home design and declare it as the current FPS design."""
        cmdKeys = cmd.cmd.keywords

        genVisit0 = genVisit0 and 'skipGenVisit0' not in cmdKeys
        designId = self._runFpsCreateDesign(f'createHomeDesign all')
        self.actor.declareFpsDesign(cmd, designId, genVisit0=genVisit0)

        if doFinish:
            cmd.finish()

        return designId
