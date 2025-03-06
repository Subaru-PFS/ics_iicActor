from importlib import reload

import ics.iicActor.sequenceList.ag as agSequence
import ics.iicActor.utils.lib as iicUtils
import ics.iicActor.utils.translate as translate
import opscore.protocols.keys as keys
import opscore.protocols.types as types
from ics.utils.threading import singleShot
from iicActor.utils.engine import ExecMode

reload(agSequence)
reload(iicUtils)


class AgCmd(object):

    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor
        self.focusSweep = None
        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('acquireField', f'[@(otf)] [<designId>] [<exptime>] [<magnitude>] [@(guideOff)] [@(dryRun)] [<fit_dScale>] [<fit_dInR>] [<exposure_delay>] [<tec_off>] {translate.seqArgs}', self.acquireField),
            ('autoguideStart', f'[@(otf)] [<designId>] [<exptime>] [<cadence>] [<center>] [<magnitude>] [@(fromSky)] [@(dryRun)] [<fit_dScale>] [<fit_dInR>] [<exposure_delay>] [<tec_off>] {translate.seqArgs}', self.autoguideStart),
            ('autoguideStop', '', self.autoguideStop),
            ('startAgFocusSweep', f'[@(otf)] [<designId>] [<exptime>] [<fit_dScale>] [<fit_dInR>] [<exposure_delay>] [<tec_off>] {translate.seqArgs}', self.startAgFocusSweep),
            ('addAgFocusPosition', '', self.addAgFocusPosition),
            ('finishAgFocusSweep', '', self.finishAgFocusSweep),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("iic_ag", (1, 1),
                                        keys.Key('name', types.String(), help='iic_sequence name'),
                                        keys.Key('comments', types.String(), help='iic_sequence comments'),
                                        keys.Key('groupId', types.Int(), help='optional groupId'),
                                        keys.Key('head', types.String() * (1,), help='cmdStr list to process before'),
                                        keys.Key('tail', types.String() * (1,), help='cmdStr list to process after'),
                                        keys.Key("designId", types.Long(),
                                                 help="pfsDesignId for the field, which defines the fiber positions"),
                                        # exptime is an integer for ag but argument type must be consistent for all commands.
                                        keys.Key('exptime', types.Float() * (1,), help='exposure time in millisecond'),
                                        keys.Key("magnitude", types.Float()),
                                        keys.Key("cadence", types.Int()),
                                        keys.Key("center", types.Float() * (1, 3)),
                                        keys.Key('fit_dScale', types.String(), help='do fit dScale (yes|no)'),
                                        keys.Key('fit_dInR', types.String(), help='do fit dInR (yes|no)'),
                                        keys.Key("exposure_delay", types.Int(), help='delay in milliseconds between AG cameras'),
                                        keys.Key('tec_off', types.String(), help='AG cameras thermoelectric coolers turned off'))
    @property
    def engine(self):
        return self.actor.engine

    def acquireField(self, cmd):
        """
        `iic acquireField [@otf] [designId=???] [exptime=???] [magnitude=???] [@guideOff] [@dryRun] [name=\"SSS\"] [comments=\"SSS\"]`

        Ag acquire field

        Parameters
        ---------
        otf : `bool`
            on the fly mode.
        designId : `int`
           optional pfsDesignId.
        exptime : `int`
           optional exposure time(ms), default(2000).
        magnitude : `float`
           magnitude limit, default(20).
        guideOff : `bool`
            deactivate telescope autoguiding to acquire a field.
        dryRun : `bool`
           dryRun command.
        name : `str`
           To be inserted in opdb:iic_sequence.name.
        comments : `str`
           To be inserted in opdb:iic_sequence.comments.
        """
        cmdKeys = cmd.cmd.keywords

        acquireField = agSequence.AcquireField.fromCmdKeys(self.actor, cmdKeys)
        self.engine.runInThread(cmd, acquireField)

    def autoguideStart(self, cmd):
        """
        `iic autoguideStart [@otf] [exptime=???] [cadence=???] [center=???] [magnitude=???] [@guideOff] [@dryRun] [name=\"SSS\"] [comments=\"SSS\"]`

        Ag autoguide start.

        Parameters
        ---------
        otf : `bool`
            on the fly mode.
        designId : `int`
           optional pfsDesignId.
        exptime : `int`
           optional exposure time(ms).
        cadence : `int`
           autoguiding cadense(ms), default(0).
        center : 3*`float`
           ra,dec,pa
        magnitude : `float`
           magnitude limit, default(20).
        fromSky : `bool`
           specifies whether (any) detected stellar objects from an initial exposure are used as a guide instead.
        dryRun : `bool`
           dryRun command.
        name : `str`
           To be inserted in opdb:iic_sequence.name.
        comments : `str`
           To be inserted in opdb:iic_sequence.comments.
        """
        cmdKeys = cmd.cmd.keywords

        autoguideStart = agSequence.AutoguideStart.fromCmdKeys(self.actor, cmdKeys)
        self.engine.runInThread(cmd, autoguideStart)

    def autoguideStop(self, cmd):
        """
        `iic autoguideStop`

        Ag stop autoguiding.
        """
        cmdKeys = cmd.cmd.keywords

        autoguideStop = agSequence.AutoguideStop.fromCmdKeys(self.actor, cmdKeys)
        self.engine.runInThread(cmd, autoguideStop)

    def startAgFocusSweep(self, cmd):
        """
        `iic startAgFocusSweep [expTime=FF.F] [nExposures=N]`

        Start an AG Focus sweep acquisition.

        Parameters
        ---------
        expTime : `float`
            MCS Exposure time.
        nExposures: `int`
            Number of exposure.
        """
        if self.focusSweep is not None:
            cmd.fail('text="there is already a focus sweep running"')
            return

        self.focusSweep = agSequence.FocusSweep.fromCmdKeys(self.actor, cmd.cmd.keywords)
        # doing startup manually, that will get a visit.
        self.engine.run(cmd, self.focusSweep, mode=ExecMode.CHECKIN)

    @singleShot
    def addAgFocusPosition(self, cmd):
        """
        `iic addAgFocusPosition`

        Acquire data for a new focus position.
        """
        if self.focusSweep is None:
            cmd.fail('text="no focus sweep to add position to"')
            return

        # setting sequence status back to ready, hard amend because flexibility.
        self.focusSweep.setCmd(cmd)
        self.focusSweep.status.hardAmend()

        # add position and run.
        self.focusSweep.addPosition()
        self.engine.run(cmd, self.focusSweep, mode=ExecMode.EXECUTE)

    @singleShot
    def finishAgFocusSweep(self, cmd):
        """
        `iic finishAgFocusSweep`

        Close out the focusSweep acquisition.
        """
        if self.focusSweep is None:
            cmd.fail('text="no focus sweep to finish"')
            return

        # just finalize the sequence.
        self.focusSweep.finalize()

        cmd.finish(f'text="AgFocusSweep iic_sequence_id:{self.focusSweep.sequence_id} visitId:{self.focusSweep.visit.visitId} now finished..."')
        # Making sure that visitId won't be used ever again.
        self.actor.visitManager.getField().lockVisit()
        # no further reference to the object.
        self.focusSweep = None