from importlib import reload

import ics.iicActor.ag.sequenceList as agSequence
import ics.iicActor.utils.lib as iicUtils
import opscore.protocols.keys as keys
import opscore.protocols.types as types
from ics.utils.threading import singleShot

reload(agSequence)
reload(iicUtils)


class AgCmd(object):

    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        seqArgs = '[<name>] [<comments>]'
        self.vocab = [
            ('acquireField',
             f'[<designId>] [<exptime>] [<magnitude>] [@(guideOff)] [@(dryRun)] {seqArgs}', self.acquireField),
            ('autoguideStart',
             f'[<designId>] [<exptime>] [<cadence>] [<center>] [<magnitude>] [@(fromSky)] [@(dryRun)] {seqArgs}',
             self.autoguideStart),
            ('autoguideStop', '', self.autoguideStop),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("iic_iic", (1, 1),
                                        keys.Key('name', types.String(), help='iic_sequence name'),
                                        keys.Key('comments', types.String(), help='iic_sequence comments'),
                                        keys.Key("designId", types.Long(),
                                                 help="pfsDesignId for the field, which defines the fiber positions"),
                                        keys.Key("exptime", types.Int(), help='exptime in ms'),
                                        keys.Key("magnitude", types.Float()),
                                        keys.Key("cadence", types.Int()),
                                        keys.Key("center", types.Float() * (1, 3)),
                                        )

    @property
    def resourceManager(self):
        return self.actor.resourceManager

    @singleShot
    def acquireField(self, cmd):
        """
        `iic acquireField [designId=???] [exptime=???] [magnitude=???] [@guideOff] [@dryRun] [name=\"SSS\"] [comments=\"SSS\"]`

        Ag acquire field

        Parameters
        ---------
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
        seqKwargs = iicUtils.genSequenceKwargs(cmd)

        exptime = cmdKeys['exptime'].values[0] if 'exptime' in cmdKeys else None
        magnitude = cmdKeys['magnitude'].values[0] if 'magnitude' in cmdKeys else None
        guide = 'no' if 'guideOff' in cmdKeys else None
        dryRun = 'yes' if 'dryRun' in cmdKeys else None

        # get provided designId or get current one.
        designId = cmdKeys['designId'].values[0] if 'designId' in cmdKeys else self.actor.visitor.getCurrentDesignId()

        # requesting resources, erk..
        job = self.resourceManager.request(cmd, agSequence.AcquireField)

        with self.actor.visitor.getVisit(caller='ag') as visit:
            job.instantiate(cmd, designId=designId, visitId=visit.visitId, exptime=exptime, guide=guide,
                            magnitude=magnitude, dryRun=dryRun, **seqKwargs)
            job.seq.process(cmd)

        cmd.finish()

    @singleShot
    def autoguideStart(self, cmd):
        """
        `iic autoguideStart [exptime=???] [cadence=???] [center=???] [magnitude=???] [@guideOff] [@dryRun] [name=\"SSS\"] [comments=\"SSS\"]`

        Ag autoguide start.

        Parameters
        ---------
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
        seqKwargs = iicUtils.genSequenceKwargs(cmd)

        exptime = cmdKeys['exptime'].values[0] if 'exptime' in cmdKeys else None
        cadence = cmdKeys['cadence'].values[0] if 'cadence' in cmdKeys else None
        center = cmdKeys['center'].values if 'center' in cmdKeys else None
        magnitude = cmdKeys['magnitude'].values[0] if 'magnitude' in cmdKeys else None
        fromSky = 'yes' if 'fromSky' in cmdKeys else None
        dryRun = 'yes' if 'dryRun' in cmdKeys else None

        # get provided designId or get current one.
        designId = cmdKeys['designId'].values[0] if 'designId' in cmdKeys else self.actor.visitor.getCurrentDesignId()

        # requesting resources, erk..
        job = self.resourceManager.request(cmd, agSequence.AutoguideStart)
        with self.actor.visitor.getVisit(caller='ag') as visit:
            job.instantiate(cmd, designId=designId, visitId=visit.visitId, exptime=exptime, fromSky=fromSky,
                            cadence=cadence, center=center, magnitude=magnitude, dryRun=dryRun,
                            **seqKwargs)
            job.seq.process(cmd)

        cmd.finish()

    def autoguideStop(self, cmd):
        """
        `iic autoguideStop`

        Ag stop autoguiding.
        """
        cmdVar = self.actor.cmdr.call(actor='ag', cmdStr='autoguide stop', timeLim=120, forUserCmd=cmd)

        if cmdVar.didFail:
            reply = cmdVar.replyList[-1]
            repStr = reply.keywords.canonical(delimiter=';')
            cmd.fail(repStr)
            return

        cmd.finish('text="autoguide stop OK"')
