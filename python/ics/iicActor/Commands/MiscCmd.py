from importlib import reload

import ics.iicActor.sequenceList.fps as fpsSequence
import ics.iicActor.sequenceList.misc as misc
import ics.iicActor.utils.lib as iicUtils
import ics.iicActor.utils.pfsDesign.opdb as designDB
import ics.iicActor.utils.translate as translate
import ics.utils.cmd as cmdUtils
import opscore.protocols.keys as keys
import opscore.protocols.types as types
from ics.iicActor.utils.sequenceStatus import Flag
from ics.utils.threading import singleShot

reload(iicUtils)
reload(designDB)
reload(misc)


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
            ('phiCrossing', f'[<stepSize>] [<count>] [<exptime>] [<designId>] {translate.seqArgs}', self.dotCrossing),
            ('thetaCrossing', f'[<stepSize>] [<count>] [<exptime>] [<designId>] {translate.seqArgs}', self.dotCrossing),
            ('fiberIdentification', f'[<fiberGroups>] {commonArgs}', self.fiberIdentification),
            ('nearDotConvergence', f'@(phi|theta) [<exptime>] [<designId>] [<maskFile>] {translate.seqArgs}',
             self.nearDotConvergenceCmd),
            ('genBlackDotsConfig', f'[<maskFile>] {translate.seqArgs}', self.genBlackDotsConfigCmd),
            ('dotRoach', f'[<exptime>] [<maskFile>] [@(hscLamps)] [<mode>] {identArgs} {translate.seqArgs}',
             self.dotRoach),
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

                                        keys.Key('stepSize', types.Int(), help='cobra step size in steps'),
                                        keys.Key('count', types.Int(), help='nExposure'),
                                        keys.Key('maskFile', types.String() * (1,),
                                                 help='filename containing which fibers to expose.'),
                                        keys.Key('designId', types.Long(), help='selected nearDot designId'),
                                        keys.Key('fiberGroups', types.Int() * (1,),
                                                 help='which fiberGroups to identify 2->31'),
                                        keys.Key('mode', types.String() * (1,), help='mode for dotRoach'),
                                        )

    @property
    def engine(self):
        return self.actor.engine

    @singleShot
    def nearDotConvergenceCmd(self, cmd):
        """Needs a dedicated command function for threading."""
        return self.nearDotConvergence(cmd)

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
        nearDotConvergence = misc.NearDotConvergence.fromCmdKeys(self.actor, cmdKeys, designId=designId)
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
        DotCrossing = misc.PhiCrossing if cmdName == 'phiCrossing' else misc.ThetaCrossing

        # run dotCrossing.
        dotCrossing = DotCrossing.fromCmdKeys(self.actor, cmd.cmd.keywords)
        self.engine.run(cmd, dotCrossing)

    def fiberIdentification(self, cmd):
        """"""
        fiberIdentification = misc.FiberIdentification.fromCmdKeys(self.actor, cmd.cmd.keywords)
        self.engine.runInThread(cmd, fiberIdentification)

    @singleShot
    def genBlackDotsConfigCmd(self, cmd):
        """Needs a dedicated command function for threading."""
        return self.genBlackDotsConfig(cmd)

    def genBlackDotsConfig(self, cmd):
        """"""
        cmdKeys = cmd.cmd.keywords

        maskFileArgs = translate.getMaskFileArgsFromCmd(cmdKeys, self.actor.actorConfig)

        cmdVar = self.actor.cmdr.call(actor='fps', cmdStr=f'createBlackDotDesign {maskFileArgs}'.strip(), timeLim=10)
        keys = cmdUtils.cmdVarToKeys(cmdVar)
        designId = int(keys['fpsDesignId'].values[0], 16)

        self.actor.declareFpsDesign(cmd, designId=designId)

        genPfsConfigFromMcs = fpsSequence.GenBlackDotsConfig.fromCmdKeys(self.actor, cmdKeys, designId=designId)
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
        cableBLampOn = self.actor.actorConfig['fps']['cableBLampOn']
        moveToHomeAll = fpsSequence.MoveToHome(exptime=mcsExptime, designId=homeDesignId, cableBLampOn=cableBLampOn)
        nearDotConvergence = misc.NearDotConvergence(phiCrossingDesignId, maskFile=False, goHome=False, noTweak=True,
                                                     twoStepsOff=False, exptime=mcsExptime, cableBLampOn=cableBLampOn,
                                                     shortExpOff=True, **self.actor.actorConfig['nearDotConvergence'])
        # use pfiLamps by default.
        roaching = misc.DotRoach if 'hscLamps' in cmdKeys else misc.DotRoachPfiLamps
        roachingInit = misc.DotRoachInit if 'hscLamps' in cmdKeys else misc.DotRoachInitPfiLamps
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
