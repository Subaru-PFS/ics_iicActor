from importlib import reload

import ics.iicActor.sequenceList.misc as misc
import ics.iicActor.utils.lib as iicUtils
import iicActor.utils.pfsDesign as pfsDesignUtils
import opscore.protocols.keys as keys
import opscore.protocols.types as types
from ics.utils.threading import singleShot

reload(iicUtils)
reload(pfsDesignUtils)
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
        seqArgs = '[<name>] [<comments>] [@doTest] [<groupId>] [<head>] [<tail>]'
        identArgs = '[<cam>] [<arm>] [<specNum>]'
        commonArgs = f'{identArgs} [<duplicate>] {seqArgs}'

        self.vocab = [
            ('phiCrossing', f'[<stepSize>] [<count>] [<exptime>] [<designId>] {seqArgs}', self.dotCrossing),
            ('thetaCrossing', f'[<stepSize>] [<count>] [<exptime>] [<designId>] {seqArgs}', self.dotCrossing),

            ('fiberIdentification', f'[<fiberGroups>] {commonArgs}', self.fiberIdentification),
            ('nearDotConvergence', f'@(phi|theta) [<exptime>] [<designId>] {seqArgs}', self.nearDotConvergence)

        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("iic_misc", (1, 1),
                                        keys.Key('exptime', types.Float() * (1,), help='exptime list (seconds)'),
                                        keys.Key('duplicate', types.Int(), help='exposure duplicate (1 is default)'),
                                        keys.Key('cam', types.String() * (1,), help='camera(s) to take exposure from'),
                                        keys.Key('arm', types.String() * (1,), help='arm to take exposure from'),
                                        keys.Key('specNum', types.Int() * (1,),
                                                 help='spectrograph module(s) to take exposure from'),
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
                                        )

    @property
    def engine(self):
        return self.actor.engine

    def nearDotConvergence(self, cmd, designName=None, doFinish=True):
        """"""
        cmdKeys = cmd.cmd.keywords

        designName = 'phiCrossing' if 'phi' in cmdKeys else designName
        designName = 'thetaCrossing' if 'theta' in cmdKeys else designName

        # get dotCrossing designId from opdb or use provided new one.
        if 'designId' in cmdKeys:
            designId = cmdKeys['designId'].values[0]
        else:
            designId = pfsDesignUtils.PfsDesignHandler.latestDesignIdMatchingName(designName)

        # declare/insert current design as nearDotDesign.
        pfsDesignUtils.PfsDesignHandler.declareCurrent(cmd, self.engine.visitManager, designId=designId)

        # run nearDotConvergence.
        nearDotConvergence = misc.NearDotConvergence.fromCmdKeys(self.actor, cmdKeys, designId=designId)
        self.engine.run(cmd, nearDotConvergence, doFinish=doFinish)

        return nearDotConvergence

    @singleShot
    def dotCrossing(self, cmd):
        """"""
        cmdKeys = cmd.cmd.keywords
        cmdName = cmd.cmd.name

        # converge to near dot in the first place.
        nearDotConvergence = self.nearDotConvergence(cmd, designName=cmdName, doFinish=False)
        # something happened convergence did not complete, we need to stop here.
        if nearDotConvergence.status.statusFlag != 0:
            genStatus = cmd.finish if nearDotConvergence.status.statusStr == 'finished' else cmd.fail
            genStatus('text="NearDotConvergence not completed, stopping here."')
            return

        # retrieving which crossing is required.
        DotCrossing = misc.PhiCrossing if cmdName == 'phiCrossing' else misc.ThetaCrossing

        # run dotCrossing.
        dotCrossing = DotCrossing.fromCmdKeys(self.actor, cmdKeys)
        self.engine.run(cmd, dotCrossing)

    def fiberIdentification(self, cmd):
        """"""
        cmdKeys = cmd.cmd.keywords

        fiberIdentification = misc.FiberIdentification.fromCmdKeys(self.actor, cmdKeys)
        self.engine.runInThread(cmd, fiberIdentification)
