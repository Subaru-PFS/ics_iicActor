import os

from ics.iicActor.sps.sequence import SpsSequence
from ics.iicActor.sps.timed import timedLampsSequence


class DotRoach(timedLampsSequence):
    """ fps MoveToPfsDesign command. """
    seqtype = 'dotRoach'
    dependencies = ['fps']

    def __init__(self, designId, visitId, stepSize, count, motor, nearDotConvergence, windowedFlat, cams, rootDir,
                 dotRoachConfig, keepMoving, doTest=False, **kwargs):
        timedLampsSequence.__init__(self, **kwargs)
        # constructing dataRoot
        dataRoot = os.path.join(rootDir, 'runs', str(visitId))

        # turning on the illuminators
        self.add(actor='sps', cmdStr='bia on')

        # move cobras to home
        self.add(actor='fps', cmdStr='moveToHome all', visit=visitId, timeLim=300)

        # going to nearDot pfsDesign
        self.add(actor='fps', cmdStr='moveToPfsDesign', designId=designId, visit=visitId,
                 iteration=nearDotConvergence['maxIteration'], tolerance=nearDotConvergence['tolerance'],
                 maskFile=dotRoachConfig, timeLim=300)

        # turning off the illuminators
        self.add(actor='sps', cmdStr='bia off')

        # first take one bias to niet things up.
        SpsSequence.expose(self, exptype='bias', cams=cams, doTest=doTest)

        # turning drp processing on
        self.add(actor='drp', cmdStr='startDotLoop', dataRoot=dataRoot, dotRoachConfig=dotRoachConfig,
                 keepMoving=keepMoving)

        exptime = dict(halogen=int(windowedFlat['exptime']), shutterTiming=False)
        redWindow = windowedFlat['redWindow']
        blueWindow = windowedFlat['blueWindow']

        for iterNum in range(count):
            self.expose(exptype='flat', exptime=exptime, cams=cams, doTest=doTest,
                        redWindow='%d,%d' % (redWindow['row0'], redWindow['nrows']),
                        blueWindow='%d,%d' % (blueWindow['row0'], blueWindow['nrows']))

            self.add(actor='drp', cmdStr='processDotData')

            self.add(actor='fps',
                     cmdStr=f'cobraMoveSteps {motor}', stepsize=stepSize,
                     maskFile=os.path.join(dataRoot, 'maskFiles', f'iter{iterNum}.csv'))

        # turning drp processing off
        self.tail.add(actor='drp', cmdStr='stopDotLoop')
