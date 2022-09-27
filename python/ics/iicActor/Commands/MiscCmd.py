import os
from importlib import reload

import ics.iicActor.misc.sequenceList as miscSequence
import ics.iicActor.utils.lib as iicUtils
import iicActor.utils.pfsDesign as pfsDesignUtils
import opscore.protocols.keys as keys
import opscore.protocols.types as types
import pandas as pd
from ics.utils.threading import singleShot

reload(iicUtils)
reload(pfsDesignUtils)


class MiscCmd(object):

    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        seqArgs = '[<name>] [<comments>] [@doTest]'
        identArgs = '[<cam>] [<arm>] [<sm>]'

        self.vocab = [
            ('dotRoach',
             f'[@(phi|theta)] [<stepSize>] [<count>] [<exptime>] [<maskFile>] [@(keepMoving)] [@(hscLamps)] {identArgs} {seqArgs}',
             self.dotRoaching),
            ('phiCrossing', f'[<stepSize>] [<count>] [<exptime>] [<designId>] {seqArgs}', self.dotCrossing),
            ('thetaCrossing', f'[<stepSize>] [<count>] [<exptime>] [<designId>] {seqArgs}', self.dotCrossing),
            ('fiberIdentification', f'[<groups>] [<exptime>] {identArgs} {seqArgs}', self.fiberIdentification),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("mcs_mcs", (1, 1),
                                        keys.Key('cam', types.String() * (1,), help='camera(s) to take exposure from'),
                                        keys.Key('arm', types.String() * (1,), help='arm to take exposure from'),
                                        keys.Key('sm', types.Int() * (1,),
                                                 help='spectrograph module(s) to take exposure from'),
                                        keys.Key('name', types.String(), help='iic_sequence name'),
                                        keys.Key('comments', types.String(), help='iic_sequence comments'),

                                        keys.Key('stepSize', types.Int(), help='optional visit_set_id.'),
                                        keys.Key('count', types.Int(), help='optional visit_id.'),
                                        keys.Key('exptime', types.Float(), help='optional visit_set_id.'),
                                        keys.Key('maskFile', types.String() * (1,),
                                                 help='filename containing which fibers to expose.'),
                                        keys.Key('designId', types.Long(), help='selected nearDot designId'),
                                        keys.Key('groups', types.Int() * (1,), help='which groups to identify 2->31')
                                        )

    @property
    def resourceManager(self):
        return self.actor.resourceManager

    def getFpsMaskFile(self, maskFile):
        """load MaskFile for fps moves."""
        maskFile = os.path.join(self.actor.actorConfig['maskFiles']['rootDir'], f'{maskFile}.csv')
        # testing if maskFile exists.
        df = pd.read_csv(maskFile, index_col=0)
        return maskFile

    @singleShot
    def dotRoaching(self, cmd):
        cmdKeys = cmd.cmd.keywords
        seqKwargs = iicUtils.genSequenceKwargs(cmd)

        # do the right
        if 'hscLamps' in cmdKeys:
            doConverge = False
            lamps = 'hscLamps'
            DotRoach = miscSequence.HscRoach
        else:
            doConverge = True
            lamps = 'pfiLamps'
            DotRoach = miscSequence.PfiRoach

        cmd.inform(f'text="starting dot-roaching script using {lamps}.."')

        # load config from instdata
        dotRoachConfig = self.actor.actorConfig['dotRoach']
        windowedFlatConfig = self.actor.actorConfig['windowedFlat'][lamps]

        if 'stepSize' in cmdKeys:
            dotRoachConfig.update(stepSize=cmdKeys['stepSize'].values[0])
        if 'count' in cmdKeys:
            dotRoachConfig.update(count=cmdKeys['count'].values[0])
        if 'phi' in cmdKeys:
            dotRoachConfig.update(motor='phi')
        if 'theta' in cmdKeys:
            dotRoachConfig.update(motor='theta')
        if 'exptime' in cmdKeys:
            windowedFlatConfig.update(exptime=cmdKeys['exptime'].values[0])

        keepMoving = 'keepMoving' in cmdKeys

        maskFile = cmdKeys['maskFile'].values[0] if 'maskFile' in cmdKeys else 'SM1_000'
        try:
            maskFile = self.getFpsMaskFile(maskFile)
        except:
            cmd.fail(f'text="failed to open maskFile file:{maskFile} !"')
            return

        if doConverge:
            mcsConfig = self.actor.actorConfig['mcs']
            nearDotConvergenceConfig = self.actor.actorConfig['nearDotConvergence']
            nearDotConvergenceConfig.update(exptime=mcsConfig['exptime'])
            # retrieve designId from config
            designId = pfsDesignUtils.PfsDesignHandler.latestDesignId(designName=f"{dotRoachConfig['motor']}Crossing")

            # declare current design as nearDotDesign.
            pfsDesignUtils.PfsDesignHandler.declareCurrent(cmd, self.actor.visitor, designId=designId)

            with self.actor.visitor.getVisit(caller='fps') as visit:
                job1 = self.resourceManager.request(cmd, miscSequence.NearDotConvergence)
                job1.instantiate(cmd, designId=designId, visitId=visit.visitId, maskFile=maskFile,
                                 **nearDotConvergenceConfig, isMainSequence=False, **seqKwargs)
                try:
                    job1.seq.process(cmd)
                finally:
                    # nearDotConvergence book-keeping.
                    job1.seq.insertVisitSet(visit.visitId)

        # We should be nearDot at this point, so we can start the actual dotRoaching.
        with self.actor.visitor.getVisit(caller='sps') as visit:
            job2 = self.resourceManager.request(cmd, DotRoach)
            job2.instantiate(cmd, visitId=visit.visitId, maskFile=maskFile, keepMoving=keepMoving,
                             windowedFlatConfig=windowedFlatConfig, **dotRoachConfig, **seqKwargs)
            job2.seq.process(cmd)

        cmd.finish()

    @singleShot
    def dotCrossing(self, cmd):
        cmdKeys = cmd.cmd.keywords
        seqKwargs = iicUtils.genSequenceKwargs(cmd)

        # retrieving which crossing
        if cmd.cmd.name == 'phiCrossing':
            motor = 'phi'
            DotCrossing = miscSequence.PhiCrossing
        else:
            motor = 'theta'
            DotCrossing = miscSequence.ThetaCrossing

        mcsCamera = 'mcs'
        cmd.inform(f'text="starting {motor}-crossing using {mcsCamera} camera..."')

        # load config from instdata
        dotCrossingConfig = self.actor.actorConfig['dotCrossing']
        nearDotConvergenceConfig = self.actor.actorConfig['nearDotConvergence']
        mcsConfig = self.actor.actorConfig['mcs']
        # setting mcs exptime consistently.
        exptime = cmdKeys['exptime'].values[0] if 'exptime' in cmdKeys else mcsConfig['exptime']
        nearDotConvergenceConfig.update(exptime=exptime)
        dotCrossingConfig.update(exptime=exptime)

        if 'stepSize' in cmdKeys:
            dotCrossingConfig.update(stepSize=cmdKeys['stepSize'].values[0])
        if 'count' in cmdKeys:
            dotCrossingConfig.update(count=cmdKeys['count'].values[0])

        # get designId from opdb or provided one.
        if 'designId' in cmdKeys:
            designId = cmdKeys['designId'].values[0]
        else:
            designId = pfsDesignUtils.PfsDesignHandler.latestDesignId(designName=f"{motor}Crossing")

        # declare current design as nearDotDesign.
        pfsDesignUtils.PfsDesignHandler.declareCurrent(cmd, self.actor.visitor, designId=designId)

        with self.actor.visitor.getVisit(caller='fps') as visit:
            job1 = self.resourceManager.request(cmd, miscSequence.NearDotConvergence)
            job1.instantiate(cmd, designId=designId, visitId=visit.visitId,
                             **nearDotConvergenceConfig, isMainSequence=False, **seqKwargs)
            try:
                job1.seq.process(cmd)
            finally:
                # nearDotConvergence book-keeping.
                job1.seq.insertVisitSet(visit.visitId)

        with self.actor.visitor.getVisit(caller='fps') as visit:
            # We should be nearDot at this point, so we can start the actual dotCrossing.
            job2 = self.resourceManager.request(cmd, DotCrossing)
            job2.instantiate(cmd, visit=visit, **dotCrossingConfig, **seqKwargs)
            try:
                job2.seq.process(cmd)
            finally:
                # useful for blackDotOptimization
                job2.seq.insertVisitSet(visit.visitId)
                self.actor.visitor.finishField()

        cmd.finish()

    @singleShot
    def fiberIdentification(self, cmd):
        cmdKeys = cmd.cmd.keywords
        seqKwargs = iicUtils.genSequenceKwargs(cmd)

        cmd.inform('text="starting fiberIdentification')

        # load config from instdata
        windowedFlatConfig = self.actor.actorConfig['windowedFlat']['hscLamps']
        maskFilesRoot = self.actor.actorConfig['maskFiles']['rootDir']

        if 'exptime' in cmdKeys:
            windowedFlatConfig['windowedFlat'].update(exptime=cmdKeys['exptime'].values[0])

        groups = cmdKeys['groups'].values if 'groups' in cmdKeys else list(set(range(2, 32)) - {25})

        # We should be nearDot at this point, so we can start the actual dotRoaching.
        job2 = self.resourceManager.request(cmd, miscSequence.FiberIdentification)
        job2.instantiate(cmd, maskFilesRoot=maskFilesRoot, groups=groups, windowedFlatConfig=windowedFlatConfig,
                         **seqKwargs)
        job2.seq.process(cmd)

        cmd.finish()
