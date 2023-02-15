import iicActor.utils.translate as translate
from ics.iicActor.utils.sequence import Sequence
from ics.iicActor.utils.visited import VisitedCmd, VisitedSequence


class AgVisitedCmd(VisitedCmd):
    visitCmdArg = 'visit_id'


class AgSequence(VisitedSequence):
    """Place holder for ag sequence."""
    caller = 'ag'

    def instantiate(self, actor, cmdStr, parseVisit=False, parseFrameId=False, **kwargs):
        """I have to redefine this because visit argument is spelled differently for ag."""
        return AgVisitedCmd(self, actor, cmdStr, parseVisit=parseVisit, parseFrameId=parseFrameId, **kwargs)


class AcquireField(AgSequence):
    """ fps MoveToPfsDesign command. """
    seqtype = 'acquireField'

    def __init__(self, designId, exptime, guide, magnitude, fit_dScale, dryRun, **seqKeys):
        AgSequence.__init__(self, **seqKeys)

        self.add('ag', 'acquire_field', parseVisit=True,
                 design_id=designId, exposure_time=exptime, guide=guide, magnitude=magnitude, fit_dscale=fit_dScale,
                 dry_run=dryRun)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        seqKeys = translate.seqKeys(cmdKeys)

        exptime = int(cmdKeys['exptime'].values[0]) if 'exptime' in cmdKeys else None
        magnitude = cmdKeys['magnitude'].values[0] if 'magnitude' in cmdKeys else None
        guide = 'no' if 'guideOff' in cmdKeys else None
        dryRun = 'yes' if 'dryRun' in cmdKeys else None
        fit_dScale = 'yes' if iicActor.actorConfig['ag']['fit_dScale'] else 'no'

        # get provided designId or get current one.
        if 'designId' in cmdKeys:
            designId = cmdKeys['designId'].values[0]
        else:
            designId = iicActor.engine.visitManager.getCurrentDesignId()

        return cls(designId, exptime, guide, magnitude, fit_dScale, dryRun, **seqKeys)


class AutoguideStart(AgSequence):
    """ fps MoveToPfsDesign command. """
    seqtype = 'autoguideStart'

    def __init__(self, designId, exptime, fromSky, cadence, center, magnitude, fit_dScale, dryRun, **seqKeys):
        AgSequence.__init__(self, **seqKeys)

        self.add('ag', 'autoguide start', parseVisit=True,
                 design_id=designId, exposure_time=exptime, from_sky=fromSky, cadence=cadence, center=center,
                 magnitude=magnitude, fit_dscale=fit_dScale, dry_run=dryRun)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        seqKeys = translate.seqKeys(cmdKeys)
        exptime = int(cmdKeys['exptime'].values[0]) if 'exptime' in cmdKeys else None
        cadence = cmdKeys['cadence'].values[0] if 'cadence' in cmdKeys else None
        center = cmdKeys['center'].values if 'center' in cmdKeys else None
        magnitude = cmdKeys['magnitude'].values[0] if 'magnitude' in cmdKeys else None
        fromSky = 'yes' if 'fromSky' in cmdKeys else None
        dryRun = 'yes' if 'dryRun' in cmdKeys else None
        fit_dScale = 'yes' if iicActor.actorConfig['ag']['fit_dScale'] else 'no'

        # get provided designId or get current one.
        if 'designId' in cmdKeys:
            designId = cmdKeys['designId'].values[0]
        else:
            designId = iicActor.engine.visitManager.getCurrentDesignId()

        return cls(designId, exptime, fromSky, cadence, center, magnitude, fit_dScale, dryRun, **seqKeys)


class AutoguideStop(Sequence):
    """ fps MoveToPfsDesign command. """
    seqtype = 'autoguideStop'

    def __init__(self, **seqKeys):
        Sequence.__init__(self, **seqKeys)
        self.add(actor='ag', cmdStr='autoguide stop')

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        seqKeys = translate.seqKeys(cmdKeys)
        return cls(**seqKeys)
