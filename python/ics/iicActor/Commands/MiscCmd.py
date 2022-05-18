from importlib import reload
import pandas as pd
import os
import ics.iicActor.misc.sequenceList as miscSequence
import ics.iicActor.utils.lib as iicUtils
import ics.utils.opdb as opdb
import opscore.protocols.keys as keys
import opscore.protocols.types as types

reload(iicUtils)


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
            ('dotRoach', f'[@(keepMoving)] [<stepSize>] [<count>] [<exptime>] [<dotRoachConfig>] {identArgs} {seqArgs}',
             self.dotRoaching),

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
                                        keys.Key('dotRoachConfig', types.String() * (1,),
                                                 help='filename containing which fibers to expose.'),
                                        )

    @property
    def resourceManager(self):
        return self.actor.resourceManager

    def dotRoaching(self, cmd):
        cmdKeys = cmd.cmd.keywords
        seqKwargs = iicUtils.genSequenceKwargs(cmd)

        cmd.inform('text="starting dot-roaching script..."')

        # load config from instdata
        config = self.actor.actorConfig['dotRoach']
        if 'stepSize' in cmdKeys:
            config.update(stepSize=cmdKeys['stepSize'].values[0])
        if 'count' in cmdKeys:
            config.update(count=cmdKeys['count'].values[0])
        if 'exptime' in cmdKeys:
            config['windowedFlat'].update(exptime=cmdKeys['exptime'].values[0])

        configRoot = config.pop('configRoot')

        keepMoving = 'keepMoving' in cmdKeys
        dotRoachConfig = cmdKeys['dotRoachConfig'].values[0] if 'dotRoachConfig' in cmdKeys else 'SM1_000'
        dotRoachConfig = os.path.join(configRoot, f'{dotRoachConfig}.csv')
        # testing if dotRoachConfig exists.
        try:
            df = pd.read_csv(dotRoachConfig, index_col=0)
        except:
            cmd.fail(f'text="failed to open dotRoachConfig file :{dotRoachConfig}!')
            return

        # retrieving designId from opdb
        try:
            [designId, ] = opdb.opDB.fetchone(
                "select pfs_design_id from pfs_design where design_name='nearDot' order by designed_at desc limit 1")
        except:
            raise RuntimeError('could not retrieve near-dot designId from opdb')

        # declaring new field
        pfsDesign, visit = self.actor.visitor.declareNewField(designId)

        job = self.resourceManager.request(cmd, miscSequence.DotRoach)
        job.instantiate(cmd, designId=designId, visitId=visit.visitId, keepMoving=keepMoving,
                        dotRoachConfig=dotRoachConfig, **config,
                        **seqKwargs)

        job.fire(cmd)
