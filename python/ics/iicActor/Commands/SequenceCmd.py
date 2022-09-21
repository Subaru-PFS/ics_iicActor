import opscore.protocols.keys as keys
import opscore.protocols.types as types
import pandas as pd
from ics.utils.opdb import opDB


class SequenceCmd(object):

    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('sequenceStatus', '[<id>]', self.sequenceStatus),
            ('sequence', '@abort [<id>]', self.abortSequence),
            ('sequence', '@finish [<id>]', self.finishSequence),
            ('sps', '@abortExposure [<id>]', self.abortExposure),
            ('sps', '@finishExposure [@(now)] [<id>]', self.finishExposure),
            ('annotate', '@(bad|ok) [<notes>] [<visit>] [<visitSet>] [<cam>] [<arm>] [<sm>]', self.annotate),
            ('getGroupId', '<groupName> [(@continue)]', self.getGroupId)
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("mcs_mcs", (1, 1),
                                        keys.Key('id', types.Int(), help='optional visit_set_id.'),
                                        keys.Key('visit', types.Int(), help='optional visit_id.'),
                                        keys.Key('visitSet', types.Int(), help='optional visit_set_id.'),
                                        keys.Key('cam', types.String() * (1,), help='camera(s)'),
                                        keys.Key('sm', types.Int() * (1,), help='spectrograph module(s)'),
                                        keys.Key('arm', types.String() * (1,), help='spspectrograph arm'),
                                        keys.Key('notes', types.String() * (1,), help='additional notes'),
                                        keys.Key('groupName', types.String(), help='group identifier'),
                                        )

    @property
    def resourceManager(self):
        return self.actor.resourceManager

    def getGroupId(self, cmd):
        """
        `iic getGroupId [continue]`

        Get new groupId or current if continue.

        Parameters
        ---------
        id : `int`
           optional sequenceId.
        """
        cmdKeys = cmd.cmd.keywords
        doContinue = 'continue' in cmdKeys
        groupName = cmdKeys['groupName'].values[0]

        groupId = self.resourceManager.requestGroupId(groupName, doContinue=doContinue)
        cmd.finish(f'groupId={groupId}')

    def findOnGoingJob(self, cmd):
        cmdKeys = cmd.cmd.keywords
        identifier = cmdKeys['id'].values[0] if 'id' in cmdKeys else None

        job = self.resourceManager.identify(identifier=identifier)
        if job.isDone:
            raise RuntimeError('job already finished')

        return job

    def sequenceStatus(self, cmd):
        """
        `iic sequenceStatus [id=N]`

        get IIC sequence status

        Parameters
        ---------
        id : `int`
           optional sequenceId.
        """
        cmdKeys = cmd.cmd.keywords
        visitSetId = cmdKeys['id'].values[0] if 'id' in cmdKeys else None

        self.actor.resourceManager.genStatus(cmd, visitSetId=visitSetId)
        cmd.finish()

    def abortSequence(self, cmd):
        """
        `iic sequence abort id=N`

        abort iic sequence.

        Parameters
        ---------
        id : `int`
           optional sequenceId.
        """
        job = self.findOnGoingJob(cmd)
        cmd.inform(f'text="aborting sequence(id:{job.visitSetId})..."')
        job.abort(cmd)

        cmd.finish()

    def finishSequence(self, cmd):
        """
        `iic sequence finish id=N`

        finish iic sequence.

        Parameters
        ---------
        id : `int`
           optional sequenceId.
        """
        job = self.findOnGoingJob(cmd)
        cmd.inform(f'text="finishing sequence(id:{job.visitSetId})..."')
        job.finish(cmd)

        cmd.finish()

    def abortExposure(self, cmd):
        """
        `iic sps @abort [id=N]`

        abort current sps exposure.

        Parameters
        ---------
        id : `int`
           optional sequenceId.
        """
        cmdKeys = cmd.cmd.keywords
        identifier = cmdKeys['id'].values[0] if 'id' in cmdKeys else 'sps'

        job = self.resourceManager.identify(identifier=identifier)
        if job.isDone:
            raise RuntimeError('job already finished')

        cmd.inform(f'text="aborting exposure from sequence(id:{job.visitSetId})..."')
        job.abort(cmd)

        cmd.finish()

    def finishExposure(self, cmd):
        """
        `iic sps @finishExposure [now] [id=N]`

        finish current sps exposure.

        Parameters
        ---------
        id : `int`
           optional sequenceId.
        """
        cmdKeys = cmd.cmd.keywords
        identifier = cmdKeys['id'].values[0] if 'id' in cmdKeys else 'sps'
        noSunssBias = 'noSunssBias' in cmdKeys
        now = 'now' in cmdKeys

        job = self.resourceManager.identify(identifier=identifier)
        if job.isDone:
            raise RuntimeError('job already finished')

        cmd.inform(f'text="finalizing exposure from sequence(id:{job.visitSetId})..."')
        job.finish(cmd, now=now, noSunssBias=noSunssBias)

        cmd.finish()

    def annotate(self, cmd):
        """
        `iic annotate bad|ok [notes=???] [visit=N] [visitSet=N] [cam=???] [arm=???] [sm=???]`

        annotate given visit or visitSet.

        Parameters
        ---------
        notes : `str`
            list of command to be describe the sequence.
        visit : `int`
           visitId to annotate.
        visitSet : `int`
           visitSetId to annotate
        cam : list of `str`
           specify which camera is/are involved
        arm : list of `str`
           specify which arm is/are involved
        sm : list of `int`
           specify which spectrograph module is/are involved
        """
        def select(column, values):
            return ' or '.join([f"{column}=='{value}'" for value in values])

        cmdKeys = cmd.cmd.keywords

        if 'visitSet' in cmdKeys:
            visitSetId = cmdKeys['visitSet'].values[0]
            visits = opDB.fetchall(f'select pfs_visit_id from visit_set where visit_set_id={visitSetId}')[:, 0]
        elif 'visit' in cmdKeys:
            visits = cmdKeys['visit'].values
        else:
            raise KeyError('visitSet or at least visit must at least be specified')

        spsExposures = pd.concat(
            [pd.DataFrame(opDB.fetchall(f'select pfs_visit_id,sps_exposure.sps_camera_id,sps_module_id,arm '
                                        f'from sps_exposure inner join sps_camera on'
                                        f' sps_exposure.sps_camera_id=sps_camera.sps_camera_id '
                                        f'where pfs_visit_id={pfs_visit_id}'),
                          columns=['pfs_visit_id', 'sps_camera_id', 'sps_module_id', 'arm']) for pfs_visit_id in
             visits]).reset_index(drop=True)

        spsExposures['cam'] = [f'{row.arm}{row.sps_module_id}' for j, row in spsExposures.iterrows()]

        spsExposures = spsExposures.query(select('cam', cmdKeys['cam'].values)) if 'cam' in cmdKeys else spsExposures
        spsExposures = spsExposures.query(select('sps_module_id', cmdKeys['sm'].values)) if 'sm' in cmdKeys else spsExposures
        spsExposures = spsExposures.query(select('arm', cmdKeys['arm'].values)) if 'arm' in cmdKeys else spsExposures

        if spsExposures.empty:
            raise ValueError('failed to match any exposure from specified identifier...')

        if 'ok' in cmdKeys:
            dataFlag, dataFlagStr = 0, 'OK'
        elif 'bad' in cmdKeys:
            dataFlag, dataFlagStr = 1, 'BAD'
        else:
            raise ValueError

        notes = cmdKeys['notes'].values[0] if 'notes' in cmdKeys else ''

        for j, exposure in spsExposures.iterrows():
            cmd.debug(
                f'''text="inserting data_flag={dataFlag} notes={notes} into sps_annotation where {' '.join([f'{k}={exposure[k]}' for k in spsExposures.columns])}"''')

            opDB.insert('sps_annotation',
                        pfs_visit_id=int(exposure.pfs_visit_id), sps_camera_id=int(exposure.sps_camera_id),
                        data_flag=int(dataFlag), notes=str(notes), created_at='now')

        cmd.finish(f'text="{len(spsExposures)} rows successfully inserted into sps_annotation with '
                   f'data_flag={dataFlag}({dataFlagStr}) notes={notes}"')
