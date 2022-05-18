import os

from ics.iicActor.sps.sequence import SpsSequence
from ics.iicActor.sps.timed import timedLampsSequence


class DotRoach(timedLampsSequence):
    """ fps MoveToPfsDesign command. """
    seqtype = 'dotRoach'
    dependencies = ['fps']

    def __init__(self, designId, visitId, stepSize, count, nearDotConvergence, windowedFlat, fluxMeasurements, cams,
                 keepMoving, dotRoachConfig, doTest=False, **kwargs):
        timedLampsSequence.__init__(self, **kwargs)

        # going to nearDot pfsDesign
        self.add(actor='fps', cmdStr='moveToPfsDesign', designId=designId, visit=visitId,
                 iteration=nearDotConvergence['maxIteration'], tolerance=nearDotConvergence['tolerance'],
                 maskFile=dotRoachConfig, timeLim=300)

        # turning off the illuminators
        self.add(actor='sps', cmdStr='bia off')

        # first take one bias to niet things up.
        SpsSequence.expose(self, exptype='bias', cams=cams, doTest=doTest)

        # turning drp processing on
        self.add(actor='drp', cmdStr='startDotLoop', keepMoving=keepMoving, dotRoachConfig=dotRoachConfig)

        exptime = dict(halogen=windowedFlat['exptime'], shutterTiming=False)
        redWindow = windowedFlat['redWindow']
        blueWindow = windowedFlat['blueWindow']

        for i in range(count):
            self.expose(exptype='flat', exptime=exptime, cams=cams, doTest=doTest,
                        redWindow=(redWindow['row0'], redWindow['nrows']),
                        blueWindow=(blueWindow['row0'], blueWindow['nrows']))

            self.add(actor='drp', cmdStr='processDotData')
            self.add(actor='fps',
                     cmdStr='updateDotLoop', stepsPerMove=stepSize,
                     filename=os.path.join(fluxMeasurements['dataPath'], 'current.csv'))

        # turning drp processing off
        self.tail.add(actor='drp', cmdStr='stopDotLoop')