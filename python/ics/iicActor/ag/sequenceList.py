from ics.iicActor.ag.sequence import AgSequence


class AcquireField(AgSequence):
    """ fps MoveToPfsDesign command. """
    seqtype = 'acquireField'
    dependencies = ['ag']

    def __init__(self, visitId, designId, exptime, guide, magnitude, dryRun, doTest=False, **kwargs):
        AgSequence.__init__(self, **kwargs)
        self.add(actor='ag', cmdStr='acquire_field',  design_id=designId, visit_id=visitId, exposure_time=exptime,
                 guide=guide, magnitude=magnitude, dry_run=dryRun)


class AutoguideStart(AgSequence):
    """ fps MoveToPfsDesign command. """
    seqtype = 'autoguideStart'
    dependencies = ['ag']

    def __init__(self, visitId, designId, exptime, fromSky, cadence, focus, center, magnitude, dryRun, doTest=False, **kwargs):
        AgSequence.__init__(self, **kwargs)
        self.add(actor='ag', cmdStr='autoguide start', design_id=designId, visit_id=visitId, exposure_time=exptime,
                 from_sky=fromSky, cadence=cadence, focus=focus, center=center, magnitude=magnitude, dry_run=dryRun)