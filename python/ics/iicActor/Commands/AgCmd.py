from importlib import reload

import ics.iicActor.ag.sequenceList as agSequence
import ics.iicActor.utils.lib as iicUtils
import opscore.protocols.keys as keys
import opscore.protocols.types as types

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
            ('acquireField', f'[<designId>] [<exptime>] [<guide>] [<magnitude>] {seqArgs}', self.acquireField),
            ('autoguideStart',
             f'[<designId>] [<exptime>] [<fromSky>] [<cadence>] [<focus>] [<center>] [<magnitude>] {seqArgs}',
             self.autoguideStart),
            ('autoguideStop', '', self.autoguideStop),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("iic_iic", (1, 1),
                                        keys.Key('name', types.String(), help='iic_sequence name'),
                                        keys.Key('comments', types.String(), help='iic_sequence comments'),
                                        keys.Key("exptime", types.Float()),
                                        keys.Key("guide", types.String()),
                                        keys.Key("magnitude", types.Float()),
                                        keys.Key("fromSky", types.String()),
                                        keys.Key("cadence", types.Float()),
                                        keys.Key("focus", types.String()),
                                        keys.Key("center", types.Float() * (1, 3)),
                                        keys.Key("designId", types.Long(),
                                                 help="pfsDesignId for the field,which defines the fiber positions"),
                                        )

    @property
    def resourceManager(self):
        return self.actor.resourceManager

    def acquireField(self, cmd):
        """
        `iic acquireField [exptime=???] [guide=???] [magnitude=???] [name=\"SSS\"] [comments=\"SSS\"]`

        Ag acquire field

        Parameters
        ---------
        exptime : `float`
           optional exposure time.
        guide : `str`
           yes|no.
        magnitude : `float`
           magnitude limit.
        name : `str`
           To be inserted in opdb:iic_sequence.name.
        comments : `str`
           To be inserted in opdb:iic_sequence.comments.
        """
        cmdKeys = cmd.cmd.keywords
        seqKwargs = iicUtils.genSequenceKwargs(cmd)

        if 'designId' in cmdKeys:
            designId = cmdKeys['designId'].values[0]
            visit = self.actor.visitor.getVisit('ag')
        else:
            designId, visit = self.actor.visitor.getField('ag')

        exptime = cmdKeys['exptime'].values[0] if 'exptime' in cmdKeys else None
        guide = cmdKeys['guide'].values[0] if 'guide' in cmdKeys else None
        magnitude = cmdKeys['magnitude'].values[0] if 'magnitude' in cmdKeys else None

        # requesting resources, erk..
        job = self.resourceManager.request(cmd, agSequence.AcquireField)

        job.instantiate(cmd, designId=designId, visitId=visit.visitId, exptime=exptime, guide=guide,
                        magnitude=magnitude, **seqKwargs)

        job.fire(cmd)

    def autoguideStart(self, cmd):
        """
        `iic autoguideStart [exptime=???] [fromSky=???] [cadence=???] [focus=???] [center=???] [magnitude=???] [name=\"SSS\"] [comments=\"SSS\"]`

        Ag autoguide start.

        Parameters
        ---------
        exptime : `float`
           optional exposure time.
        fromSky : `str`
           yes|no
        cadence : `float`
           cadense(ms)
        focus : `str`
           yes|no
        center : 3*`float`
           ra,dec,pa
        magnitude : `float`
           magnitude limit.
        name : `str`
           To be inserted in opdb:iic_sequence.name.
        comments : `str`
           To be inserted in opdb:iic_sequence.comments.
        """
        cmdKeys = cmd.cmd.keywords
        seqKwargs = iicUtils.genSequenceKwargs(cmd)

        exptime = cmdKeys['exptime'].values[0] if 'exptime' in cmdKeys else None
        fromSky = cmdKeys['fromSky'].values[0] if 'fromSky' in cmdKeys else None
        cadence = cmdKeys['cadence'].values[0] if 'cadence' in cmdKeys else None
        focus = cmdKeys['focus'].values[0] if 'focus' in cmdKeys else None
        center = cmdKeys['center'].values if 'center' in cmdKeys else None
        magnitude = cmdKeys['magnitude'].values[0] if 'magnitude' in cmdKeys else None

        if 'designId' in cmdKeys:
            designId = cmdKeys['designId'].values[0]
            visit = self.actor.visitor.getVisit('ag')
        else:
            designId, visit = self.actor.visitor.getField('ag')

        # requesting resources, erk..
        job = self.resourceManager.request(cmd, agSequence.AutoguideStart)
        job.instantiate(cmd, designId=designId, visitId=visit.visitId, exptime=exptime, fromSky=fromSky,
                        cadence=cadence, focus=focus, center=center, magnitude=magnitude, **seqKwargs)

        job.fire(cmd)

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
