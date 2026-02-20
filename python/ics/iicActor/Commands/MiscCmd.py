from importlib import reload

import ics.iicActor.sequenceList.fps as fpsSequenceList
import ics.iicActor.sequenceList.misc as miscSequenceList
import ics.iicActor.sequenceList.sps as spsSequenceList
import ics.iicActor.sps.sequence as spsSequence
import ics.iicActor.utils.lib as iicUtils
import ics.iicActor.utils.pfsDesign.opdb as designDB
import ics.iicActor.utils.translate as translate
import ics.utils.cmd as cmdUtils
import opscore.protocols.keys as keys
import opscore.protocols.types as types
from ics.iicActor.utils.sequenceStatus import Flag
from ics.utils.threading import singleShot
from opscore.utility.qstr import qstr

reload(iicUtils)
reload(designDB)
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
            ('dotRoach', f'[<exptime>] [<maskFile>] [@(hscLamps)] [<mode>] {identArgs} {translate.seqArgs}',
             self.dotRoach),
            ('thetaPhiScan', 'start', self.startNewThetaPhiScan),
            ('thetaPhiScan', f'takeNextTheta <groupId> [<thetaAngle>] [<exptime>] {identArgs} {translate.seqArgs}',
             self.takeNextThetaPhiScan)
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
        homeDesignId = designDB.latestDesignIdMatchingName('cobraHome', exact=True)
        phiCrossingDesignId = designDB.latestDesignIdMatchingName('phiCrossing-2022-06-19')

        # exptime in cmdKeys means SPS exptime but the sequence interpret it as MCS exptime, so we have to patch it.
        mcsExptime = self.actor.actorConfig['mcs']['exptime']
        illuminators = self.actor.actorConfig['illuminators']
        nearDotConvergenceConfig = {**self.actor.actorConfig['nearDotConvergence'], 'noHome': True}
        moveToHomeAll = fpsSequenceList.MoveToHome(exptime=mcsExptime, designId=homeDesignId, all=True, **illuminators)
        nearDotConvergence = fpsSequenceList.NearDotConvergence(phiCrossingDesignId,
                                                                **nearDotConvergenceConfig, **illuminators)
        # use pfiLamps by default.
        roaching = miscSequenceList.DotRoach if 'hscLamps' in cmdKeys else miscSequenceList.DotRoachPfiLamps
        roachingInit = miscSequenceList.DotRoachInit if 'hscLamps' in cmdKeys else miscSequenceList.DotRoachInitPfiLamps
        # now roaching is split in two steps.
        dotRoachInit = roachingInit.fromCmdKeys(self.actor, cmd.cmd.keywords)
        dotRoach = roaching.fromCmdKeys(self.actor, cmd.cmd.keywords)

        # first declare design and going home.
        self.actor.declareFpsDesign(cmd, designId=homeDesignId)
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

    def takeNextThetaPhiScan(self, cmd):
        """"""
        cmdKeys = cmd.cmd.keywords
        groupId = cmdKeys['groupId'].values[0]
        thetaAngle = cmdKeys['thetaAngle'].values[0] if 'thetaAngle' in cmdKeys else None
        name = f'theta_{thetaAngle:03d}'

        mcsExptime = self.actor.actorConfig['mcs']['exptime']
        illuminators = self.actor.actorConfig['illuminators']
        thetaPhiScanConfig = self.actor.actorConfig['thetaPhiScan']
        scienceTraceConfig = thetaPhiScanConfig['scienceTrace']
        moveToPfsDesignConfig = thetaPhiScanConfig['moveToPfsDesign']

        lampsKeys = dict(halogen=int(translate.resolveExptime(cmdKeys, scienceTraceConfig)),
                         iis=dict(),
                         shutterTiming=0)
        __, duplicate = translate.spsExposureKeys(cmdKeys, doRaise=False)
        windowKeys = translate.windowKeys(cmdKeys, scienceTraceConfig)

        cams = spsSequence.SpsSequence.keysToCam(self.actor, cmdKeys, configDict=scienceTraceConfig['idDict'])

        homeDesignId = self._runFpsCreateDesign(f'createHomeDesign all')
        self.actor.declareFpsDesign(cmd, designId=homeDesignId)

        moveToHomeAll = fpsSequenceList.MoveToHome(exptime=mcsExptime, designId=homeDesignId, all=True, **illuminators)
        self.engine.run(cmd, moveToHomeAll, doFinish=False)

        scienceTrace = spsSequenceList.calib.ScienceTrace(cams, lampsKeys, duplicate, windowKeys,
                                                          name=name,
                                                          comments='cobraHome')
        self.engine.run(cmd, scienceTrace, doFinish=False)

        phiAngles = thetaPhiScanConfig['phiAngles']

        for phiAngle in phiAngles:
            designName = f'thetaPhiScan_{thetaAngle:03d}_{phiAngle:03d}'

            # going to phi home
            if phiAngle == 0:
                designId = self._runFpsCreateDesign(f'createHomeDesign phi designName={designName}')
                moveCobra = fpsSequenceList.MoveToHome(designId=designId, exptime=mcsExptime, phi=True, **illuminators)
            else:
                designId = self._runFpsCreateDesign(
                    f'createThetaPhiScanDesign thetaAngle={thetaAngle:d} phiAngle={phiAngle:d} designName={designName}')
                moveCobra = fpsSequenceList.MoveToPfsDesign(designId=designId, **moveToPfsDesignConfig, **illuminators)

            self.actor.declareFpsDesign(cmd, designId=designId)
            self.engine.run(cmd, moveCobra, doFinish=False)

            scienceTrace = spsSequenceList.calib.ScienceTrace(cams, lampsKeys, duplicate, windowKeys,
                                                              name=name,
                                                              comments=designName)
            self.engine.run(cmd, scienceTrace, doFinish=False)

        cmd.finish()
