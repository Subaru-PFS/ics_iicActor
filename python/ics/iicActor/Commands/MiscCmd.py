from importlib import reload

import ics.iicActor.sequenceList.fps as fpsSequenceList
import ics.iicActor.sequenceList.misc as miscSequenceList
import ics.iicActor.sequenceList.sps as spsSequenceList
import ics.iicActor.sps.sequence as spsSequence
import ics.iicActor.utils.lib as iicUtils
import ics.iicActor.utils.translate as translate
import ics.utils.cmd as cmdUtils
import opscore.protocols.keys as keys
import opscore.protocols.types as types
from ics.iicActor.utils.sequenceStatus import Flag
from ics.utils.threading import singleShot
from opscore.utility.qstr import qstr

reload(iicUtils)

reload(miscSequenceList)


class MiscCmd(object):

    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        identArgs = '[<cam>] [<cams>] [<specNum>] [<specNums>] [<arm>] [<arms>]'
        commonArgs = f'{identArgs} [<duplicate>] {translate.seqArgs}'

        self.vocab = [
            ('fiberIdentification', f'[<fiberGroups>] {commonArgs}', self.fiberIdentification),
            ('thetaPhiScan', 'start', self.startNewThetaPhiScan),
            ('thetaPhiScan', f'takeNextTheta [<groupId>] [<thetaAngle>] [<exptime>] {identArgs} {translate.seqArgs}',
             self.takeNextThetaPhiScan),
            ('thetaPhiScan', f'takeNextPhi [<groupId>] [<phiAngle>] [<exptime>] {identArgs} {translate.seqArgs}',
             self.takeNextPhiThetaScan),
            ('declareHomeDesign', '[@skipGenVisit0]', self.declareHomeDesign),
            ('hotRoach', '[<exptime>]', self.test),
            ('dotRoach', f'[<exptime>] [hscLamps] {identArgs} {translate.seqArgs}', self.dotRoach),
            ('dotScan', f'[<exptime>] [hscLamps] {identArgs} {translate.seqArgs}', self.dotScan),
            ('dotConvergence', f'[<iteration>] {translate.seqArgs}', self.dotConvergence)
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
                                        keys.Key('hscLamps', help='use HSC lamps instead of PFI lamps'),
                                        keys.Key("thetaAngle", types.Int(), units='deg',
                                                 help="Designed theta angle (deg)"),
                                        keys.Key("phiAngle", types.Int(), units='deg',
                                                 help="Designed phi angle (deg)"),
                                        keys.Key('iteration', types.Int(),
                                                 help='convergence iterations, overriding the config'),
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

    def fiberIdentification(self, cmd):
        """"""
        fiberIdentification = miscSequenceList.FiberIdentification.fromCmdKeys(self.actor, cmd.cmd.keywords)
        self.engine.runInThread(cmd, fiberIdentification)

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

    def test(self, cmd):
        cmdKeys = cmd.cmd.keywords

        mcsExptime = self.actor.actorConfig['mcs']['exptime']
        illuminators = self.actor.actorConfig['illuminators']
        thetaPhiScanConfig = self.actor.actorConfig['thetaPhiScan']
        scienceTraceConfig = thetaPhiScanConfig['scienceTrace']
        lampsKeys = dict(halogen=int(translate.resolveExptime(cmdKeys, scienceTraceConfig)))
        __, duplicate = translate.spsExposureKeys(cmdKeys, doRaise=False)
        windowKeys = translate.windowKeys(cmdKeys, scienceTraceConfig)
        cams = spsSequence.SpsSequence.keysToCam(self.actor, cmdKeys, configDict=scienceTraceConfig['idDict'])

        homeDesignId = self._runFpsCreateDesign(f'createHomeDesign all')
        self.actor.declareFpsDesign(cmd, designId=homeDesignId)
        moveToHomeAll = fpsSequenceList.MoveToHome(exptime=mcsExptime, designId=homeDesignId, all=True, **illuminators)
        self.engine.run(cmd, moveToHomeAll, doFinish=False)

        # take one trace
        scienceTrace = spsSequenceList.calib.ScienceTrace(cams, lampsKeys, duplicate, windowKeys,
                                                          name='hotRoach',
                                                          comments='cobraHome')
        self.engine.run(cmd, scienceTrace, doFinish=False)

        # run nearDotConvergence.
        designId = self.engine.opdb.latestDesignIdMatchingName('phiCrossing-2026-03-10')
        self.actor.declareFpsDesign(cmd, designId=designId)
        nearDotConvergence = fpsSequenceList.NearDotConvergence.fromCmdKeys(self.actor, cmdKeys, designId=designId)
        self.engine.run(cmd, nearDotConvergence, doFinish=False)

        # Run fps hide
        moveToDot = fpsSequenceList.MoveToDot.fromCmdKeys(self.actor, cmdKeys)
        self.engine.run(cmd, moveToDot, doFinish=False)

        # take one trace
        scienceTrace = spsSequenceList.calib.ScienceTrace(cams, lampsKeys, duplicate, windowKeys,
                                                          name='hotRoach',
                                                          comments='after_hiding_cobras')
        self.engine.run(cmd, scienceTrace, doFinish=False)

        cmd.finish()

    @singleShot
    def dotRoach(self, cmd):
        """Hide every cobra behind its dot, correcting the ones the flux says are lit."""
        self._dotSequence(cmd, miscSequenceList.DotRoach, miscSequenceList.DotRoachPfiLamps,
                          'dotRoach')

    @singleShot
    def dotScan(self, cmd):
        """Walk the fleet across the dots to measure the obscuration curve.

        The calibration that produces cobra_dot_target.csv.  It deliberately drives every
        cobra past its optimum, so it leaves the fleet at no useful depth: not a substitute
        for dotRoach.
        """
        self._dotSequence(cmd, miscSequenceList.DotScan, miscSequenceList.DotScanPfiLamps,
                          'dotScan')

    @singleShot
    def dotConvergence(self, cmd):
        """Home the fleet and converge it near the dots, and stop there.

        The front of dotScan and dotRoach with no SPS in it, so the convergence can be
        exercised on its own: it moves cobras and writes a run directory, which is what
        a change to the convergence has to be judged on, without spending flats.
        """
        cmdKeys = cmd.cmd.keywords
        iteration = cmdKeys['iteration'].values[0] if 'iteration' in cmdKeys else None

        if not self._dotHome(cmd):
            return
        if self._dotConverge(cmd, 'dotScan', iteration=iteration) is None:
            return

        cmd.finish('text="converged near the dots"')

    def _dotHome(self, cmd):
        """Drive every cobra home and re-centre the broken ones.

        Returns
        -------
        `bool`
            False once the command has been failed, so the caller can simply return.
        """
        mcsExptime = self.actor.actorConfig['mcs']['exptime']
        illuminators = self.actor.actorConfig['illuminators']

        homeDesignId = self._runFpsCreateDesign('createHomeDesign all')
        moveToHomeAll = fpsSequenceList.MoveToHome(exptime=mcsExptime, designId=homeDesignId,
                                                   all=True, updateCobrasCenters=True,
                                                   **illuminators)
        self.actor.declareFpsDesign(cmd, designId=homeDesignId)
        self.engine.run(cmd, moveToHomeAll, doFinish=False)

        if moveToHomeAll.status.flag != Flag.FINISHED:
            cmd.fail('text="moveToHome not completed, stopping here."')
            return False

        return True

    def _dotConverge(self, cmd, configKey, iteration=None):
        """Run the near-dot ramp, leaving the fleet at this sequence's landing depth.

        Called after the fleet is home and, in the full sequences, after the reference
        flat: the ramp hides most cobras, so nothing that needs to see them lit can run
        afterwards.

        Parameters
        ----------
        cmd : the command being served; failed on error before returning.
        configKey : `str`
            actorConfig section holding this sequence's convergence overrides, so the
            scan and the roach can land at different depths.
        iteration : `int`, optional
            Overrides the configured count.  The ramp divides its run-up by the number
            of iterations, so changing it changes the step size, not just how long the
            fleet is given.

        Returns
        -------
        `int` or None
            The dot design converged against, or None once the command has been failed.
        """
        illuminators = self.actor.actorConfig['illuminators']
        overrides = self.actor.actorConfig.get(configKey, {}).get('nearDotConvergence', {})
        nearDotConvergenceConfig = {**self.actor.actorConfig['nearDotConvergence'],
                                    **overrides, 'noHome': True}
        if iteration is not None:
            nearDotConvergenceConfig['nIteration'] = iteration

        dotDesignId = self._runFpsCreateDesign('createDotConvergenceDesign')
        nearDotConvergence = fpsSequenceList.NearDotConvergence(dotDesignId,
                                                                **nearDotConvergenceConfig,
                                                                **illuminators)
        self.actor.declareFpsDesign(cmd, designId=dotDesignId)
        self.engine.run(cmd, nearDotConvergence, doFinish=False)

        if nearDotConvergence.status.flag != Flag.FINISHED:
            cmd.fail('text="NearDotConvergence not completed, stopping here."')
            return None

        return dotDesignId

    def _dotSequence(self, cmd, HscRoach, PfiRoach, configKey):
        """Home, initialise, converge near the dots, then run the flat sequence.

        Parameters
        ----------
        cmd : the command being served
        HscRoach, PfiRoach : the flat sequence to run, per illuminator
        configKey : `str`
            actorConfig section holding this sequence's convergence overrides, so the
            scan and the roach can land at different depths.
        """
        cmdKeys = cmd.cmd.keywords

        RoachInit = miscSequenceList.DotRoachInit if 'hscLamps' in cmdKeys else miscSequenceList.DotRoachInitPfiLamps
        dotRoachInit = RoachInit.fromCmdKeys(self.actor, cmd.cmd.keywords)

        Roach = HscRoach if 'hscLamps' in cmdKeys else PfiRoach
        dotRoach = Roach.fromCmdKeys(self.actor, cmdKeys)

        # Step 1: drive all cobras home.
        if not self._dotHome(cmd):
            return

        # Step 2: the reference flat, which has to see the cobras still lit -- so it
        # belongs here, between homing and the ramp that hides them.
        self.engine.run(cmd, dotRoachInit, doFinish=False)

        if dotRoachInit.status.flag != Flag.FINISHED:
            if cmd.alive:
                cmd.fail('text="dotRoachInit not completed, stopping here."')
            return

        # Step 3: converge to near-dot position.
        if self._dotConverge(cmd, configKey) is None:
            return

        # Step 4: open-loop flux-based scan across the dot, starting from the ramp landing
        # the convergence left the fleet at.
        self.engine.run(cmd, dotRoach, doFinish=False)

        if dotRoach.status.flag != Flag.FINISHED:
            if cmd.alive:
                cmd.fail('text="dotRoach not completed, stopping here."')
            return

        cmd.finish(f'text="{configKey} finished"')
