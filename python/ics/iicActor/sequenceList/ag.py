import ics.iicActor.utils.opdb as opdbUtils
import ics.iicActor.utils.translate as translate
from ics.iicActor.utils.sequence import Sequence
from ics.iicActor.utils.visited import VisitedCmd, VisitedSequence


class AgVisitedCmd(VisitedCmd):
    visitCmdArg = 'visit_id'


class AgSequence(VisitedSequence):
    """Placeholder for ag sequence."""
    caller = 'ag'
    insertVisitSet = False

    def instantiate(self, actor, cmdStr, parseVisit=False, parseFrameId=False, **kwargs):
        """I have to redefine this because visit argument is spelled differently for ag."""
        return AgVisitedCmd(self, actor, cmdStr, parseVisit=parseVisit, parseFrameId=parseFrameId, **kwargs)

    def finalize(self):
        VisitedSequence.finalize(self)
        # ag command are ignored when it comes to visit_set, so making it happen manually.
        if self.insertVisitSet:
            opdbUtils.insertVisitSet(self.seqtype, sequence_id=self.sequence_id, pfs_visit_id=self.visit.visitId)


class AcquireField(AgSequence):
    """ fps MoveToPfsDesign command. """
    seqtype = 'acquireField'

    def __init__(self, designId, exptime, guide, magnitude, dryRun, fit_dScale, fit_dInR, exposure_delay, tec_off,
                 visit0, **seqKeys):
        AgSequence.__init__(self, **seqKeys)

        self.add('ag', 'acquire_field', parseVisit=True,
                 design_id=designId, exposure_time=exptime, guide=guide, magnitude=magnitude, dry_run=dryRun,
                 fit_dscale=fit_dScale, fit_dinr=fit_dInR, exposure_delay=exposure_delay, tec_off=tec_off,
                 visit0=visit0)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct ScienceObject object."""
        seqKeys = translate.seqKeys(cmdKeys)

        exptime = int(cmdKeys['exptime'].values[0]) if 'exptime' in cmdKeys else None
        guide = 'no' if 'guideOff' in cmdKeys else None
        magnitude = cmdKeys['magnitude'].values[0] if 'magnitude' in cmdKeys else None
        dryRun = 'yes' if 'dryRun' in cmdKeys else None
        fit_dScale = cmdKeys['fit_dScale'].values[0] if 'fit_dScale' in cmdKeys else None
        fit_dInR = cmdKeys['fit_dInR'].values[0] if 'fit_dInR' in cmdKeys else None
        exposure_delay = cmdKeys['exposure_delay'].values[0] if 'exposure_delay' in cmdKeys else None
        tec_off = cmdKeys['tec_off'].values[0] if 'tec_off' in cmdKeys else None

        # get provided designId or get current one.
        if 'designId' in cmdKeys:
            designId = cmdKeys['designId'].values[0]
        else:
            designId = iicActor.visitManager.getCurrentDesignId()

        # Grabbing visit0 if possible.
        visit0 = False
        pfsConfig0 = iicActor.visitManager.getField().pfsConfig0
        visit0 = pfsConfig0.visit if pfsConfig0 and pfsConfig0.pfsDesignId == designId else visit0

        return cls(designId, exptime, guide, magnitude, dryRun, fit_dScale, fit_dInR, exposure_delay, tec_off, visit0,
                   **seqKeys)


class AutoguideStart(AgSequence):
    """ fps MoveToPfsDesign command. """
    seqtype = 'autoguideStart'

    def __init__(self, designId, fromSky, exptime, cadence, center, magnitude, dryRun, fit_dScale, fit_dInR,
                 exposure_delay, tec_off, max_correction, visit0, **seqKeys):
        AgSequence.__init__(self, **seqKeys)

        self.add('ag', 'autoguide start', parseVisit=True,
                 design_id=designId, exposure_time=exptime, cadence=cadence, center=center, magnitude=magnitude,
                 from_sky=fromSky, dry_run=dryRun, fit_dscale=fit_dScale, fit_dinr=fit_dInR,
                 exposure_delay=exposure_delay, tec_off=tec_off, max_correction=max_correction, visit0=visit0)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        seqKeys = translate.seqKeys(cmdKeys)

        fromSky = 'yes' if 'fromSky' in cmdKeys else None
        exptime = int(cmdKeys['exptime'].values[0]) if 'exptime' in cmdKeys else None
        cadence = cmdKeys['cadence'].values[0] if 'cadence' in cmdKeys else None
        center = cmdKeys['center'].values if 'center' in cmdKeys else None
        magnitude = cmdKeys['magnitude'].values[0] if 'magnitude' in cmdKeys else None
        dryRun = 'yes' if 'dryRun' in cmdKeys else None
        fit_dScale = cmdKeys['fit_dScale'].values[0] if 'fit_dScale' in cmdKeys else None
        fit_dInR = cmdKeys['fit_dInR'].values[0] if 'fit_dInR' in cmdKeys else None
        exposure_delay = cmdKeys['exposure_delay'].values[0] if 'exposure_delay' in cmdKeys else None
        tec_off = cmdKeys['tec_off'].values[0] if 'tec_off' in cmdKeys else None
        max_correction = cmdKeys['max_correction'].values[0] if 'max_correction' in cmdKeys else None

        # get provided designId or get current one.
        if 'designId' in cmdKeys:
            designId = cmdKeys['designId'].values[0]
        else:
            designId = iicActor.visitManager.getCurrentDesignId()

        # Grabbing visit0 if possible.
        visit0 = False
        pfsConfig0 = iicActor.visitManager.getField().pfsConfig0
        visit0 = pfsConfig0.visit if pfsConfig0 and pfsConfig0.pfsDesignId == designId else visit0

        return cls(designId, fromSky, exptime, cadence, center, magnitude, dryRun, fit_dScale, fit_dInR,
                   exposure_delay, tec_off, max_correction, visit0, **seqKeys)


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


class FocusSweep(AgSequence):
    """The state required to run an AG focus sweep.

    Basically, the Gen2 command knows about the hexapod motion, and
    interleaves POPT2 hexapod moves with requests to us to expose.

    """
    seqtype = 'agFocusSweep'
    insertVisitSet = True

    def __init__(self, designId, exptime, fit_dScale, fit_dInR, exposure_delay, tec_off, **seqKeys):
        AgSequence.__init__(self, **seqKeys)

        self.parseKwargs = dict(design_id=designId, exposure_time=exptime, fit_dScale=fit_dScale,
                                fit_dInR=fit_dInR,
                                exposure_delay=exposure_delay, tec_off=tec_off)

    @classmethod
    def fromCmdKeys(cls, iicActor, cmdKeys):
        """Defining rules to construct FocusSweep object."""
        seqKeys = translate.seqKeys(cmdKeys)

        exptime = int(cmdKeys['exptime'].values[0]) if 'exptime' in cmdKeys else None
        fit_dScale = cmdKeys['fit_dScale'].values[0] if 'fit_dScale' in cmdKeys else None
        fit_dInR = cmdKeys['fit_dInR'].values[0] if 'fit_dInR' in cmdKeys else None
        exposure_delay = cmdKeys['exposure_delay'].values[0] if 'exposure_delay' in cmdKeys else None
        tec_off = cmdKeys['tec_off'].values[0] if 'tec_off' in cmdKeys else None

        # get provided designId or get current one.
        if 'designId' in cmdKeys:
            designId = cmdKeys['designId'].values[0]
        else:
            designId = iicActor.visitManager.getCurrentDesignId()

        # Need to get a new visit, just easier this way.
        pfsDesign, visit0 = iicActor.visitManager.declareNewField(designId, genVisit0=True)

        return cls(designId, exptime, fit_dScale, fit_dInR, exposure_delay, tec_off, **seqKeys)

    def addPosition(self):
        """Acquire data for a new focus position."""
        self.add('ag', 'acquire_field', parseVisit=True, **self.parseKwargs)
