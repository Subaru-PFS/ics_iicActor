import os
from importlib import reload

import ics.iicActor.misc.sequenceList as miscSequence
import ics.iicActor.utils.lib as iicUtils
import ics.utils.opdb as opdb
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
            ('dotRoach', f'[@(phi|theta)] [<stepSize>] [<count>] [<exptime>] [<maskFile>] [@(keepMoving)] {identArgs} {seqArgs}', self.dotRoaching),
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
                                        )

    @property
    def resourceManager(self):
        return self.actor.resourceManager

    def getNearDotDesign(self, mcsCamera, motor):
        """Retrieve nearDot design from opdb for phi|theta"""
        # retrieving designId from opdb
        designName = f"{mcsCamera}.nearDot.{motor}"

        try:
            [designId, ] = opdb.opDB.fetchone(
                f"select pfs_design_id from pfs_design where design_name='{designName}' order by designed_at desc limit 1")
        except:
            raise RuntimeError(f'could not retrieve {designName} designId from opdb')

        return designId

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

        mcsCamera = 'mcs'
        cmd.inform('text="starting dot-roaching script..."')

        # load config from instdata
        dotRoachConfig = self.actor.actorConfig['dotRoach']
        nearDotConvergenceConfig = self.actor.actorConfig['nearDotConvergence']

        if 'stepSize' in cmdKeys:
            dotRoachConfig.update(stepSize=cmdKeys['stepSize'].values[0])
        if 'count' in cmdKeys:
            dotRoachConfig.update(count=cmdKeys['count'].values[0])
        if 'exptime' in cmdKeys:
            dotRoachConfig['windowedFlat'].update(exptime=cmdKeys['exptime'].values[0])
        if 'phi' in cmdKeys:
            dotRoachConfig.update(motor='phi')
        if 'theta' in cmdKeys:
            dotRoachConfig.update(motor='theta')

        keepMoving = 'keepMoving' in cmdKeys

        maskFile = cmdKeys['maskFile'].values[0] if 'maskFile' in cmdKeys else 'SM1_000'
        try:
            maskFile = self.getFpsMaskFile(maskFile)
        except:
            cmd.fail(f'text="failed to open maskFile file:{maskFile} !"')
            return

        # retrieve designId from opdb
        designId = self.getNearDotDesign(mcsCamera, dotRoachConfig['motor'])
        # declare current design as nearDotDesign.
        pfsDesignUtils.PfsDesignHandler.declareCurrentPfsDesign(cmd, self.actor.visitor, designId=designId)

        with self.actor.visitor.getVisit(caller='fps') as visit:
            job1 = self.resourceManager.request(cmd, miscSequence.NearDotConvergence)
            job1.instantiate(cmd, designId=designId, visitId=visit.visitId, maskFile=maskFile,
                             **nearDotConvergenceConfig, isMainSequence=False, **seqKwargs)
            job1.seq.process(cmd)

        # We should be nearDot at this point, so we can start the actual dotRoaching.
        job2 = self.resourceManager.request(cmd, miscSequence.DotRoach)
        job2.instantiate(cmd, visitId=visit.visitId, maskFile=maskFile, keepMoving=keepMoving, **dotRoachConfig,
                         **seqKwargs)
        job2.seq.process(cmd)

        cmd.finish()
