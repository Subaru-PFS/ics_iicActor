import os

import ics.utils.opdb as opdb
from ics.iicActor.fps.sequence import FpsSequence
from ics.iicActor.sps.sequence import SpsSequence
from ics.iicActor.sps.timed import timedLampsSequence


class DotRoaches(timedLampsSequence, FpsSequence):
    """ fps MoveToPfsDesign command. """
    seqtype = 'dotRoaches'
    dependencies = ['fps']

    def __init__(self, stepSize, count, nearDotConvergence, windowedFlat, fluxMeasurements, cams, keepMoving, expose,
                 doTest=False, **kwargs):
        timedLampsSequence.__init__(self, **kwargs)
        # retrieving designId from opdb
        try:
            [designId, ] = opdb.opDB.fetchone(
                "select pfs_design_id from pfs_design where design_name='nearDot' order by designed_at desc limit 1")
        except:
            raise RuntimeError('could not retrieve near-dot designId from opdb')

        # going to nearDot pfsDesign
        self.moveToPfsDesign(designId=designId,
                             iteration=nearDotConvergence['maxIteration'],
                             tolerance=nearDotConvergence['tolerance'], timeLim=300)

        # turning off the illuminators
        self.add(actor='sps', cmdStr='bia off')

        # first take one bias to niet things up.
        SpsSequence.expose(self, exptype='bias', cams=cams, doTest=doTest)

        # turning drp processing on
        self.add(actor='drp', cmdStr='startDotLoop', keepMoving=keepMoving, expose=expose)

        exptime = dict(halogen=windowedFlat['exptime'], shutterTiming=False)

        for i in range(count):
            self.expose(exptype='flat', exptime=exptime, cams=cams, doTest=doTest,
                        window=(windowedFlat['row0'], windowedFlat['nrows']))
            self.add(actor='drp', cmdStr='processDotData')
            self.add(actor='fps',
                     cmdStr='updateDotLoop', stepsPerMove=stepSize,
                     filename=os.path.join(fluxMeasurements['dataPath'], 'current.csv'))

        # turning drp processing off
        self.add(actor='drp', cmdStr='stopDotLoop')
