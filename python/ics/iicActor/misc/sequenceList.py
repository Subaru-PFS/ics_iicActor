import os

from ics.iicActor.fps.sequence import FpsSequence
from ics.iicActor.sps.timed import timedLampsSequence


class NearDotConvergence(FpsSequence):
    seqtype = 'nearDotConvergence'
    dependencies = ['mcs']

    def __init__(self, designId, visitId, maxIteration, tolerance, maskFile=False, doTest=False, **kwargs):
        FpsSequence.__init__(self, **kwargs)
        # turning on the illuminators
        self.add(actor='sps', cmdStr='bia on')

        # move cobras to home
        self.add(actor='fps', cmdStr='moveToHome all', visit=visitId, timeLim=300)

        # going to nearDot pfsDesign
        self.add(actor='fps', cmdStr='moveToPfsDesign', designId=designId, visit=visitId, iteration=maxIteration,
                 tolerance=tolerance, maskFile=maskFile, timeLim=300)

        # turning off the illuminators
        self.tail.add(actor='sps', cmdStr='bia off')


class DotRoach(timedLampsSequence):
    """ fps MoveToPfsDesign command. """
    seqtype = 'dotRoach'
    dependencies = ['fps']

    def __init__(self, visitId, maskFile, keepMoving, cams, rootDir, stepSize, count, motor, windowedFlat, doTest=False,
                 **kwargs):
        timedLampsSequence.__init__(self, **kwargs)

        dataRoot = os.path.join(rootDir, f'v{str(visitId).zfill(6)}')
        maskFilesRoot = os.path.join(dataRoot, 'maskFiles')

        # use sps erase command to niet things up.
        self.add(actor='sps', cmdStr='erase', cams=cams)

        # turning drp processing on
        self.add(actor='drp', cmdStr='startDotRoach', dataRoot=dataRoot, maskFile=maskFile, keepMoving=keepMoving)

        exptime = dict(halogen=int(windowedFlat['exptime']), shutterTiming=False)
        redWindow = windowedFlat['redWindow']
        blueWindow = windowedFlat['blueWindow']

        for iterNum in range(count):
            self.expose(exptype='flat', exptime=exptime, cams=cams, doTest=doTest,
                        redWindow='%d,%d' % (redWindow['row0'], redWindow['nrows']),
                        blueWindow='%d,%d' % (blueWindow['row0'], blueWindow['nrows']))

            self.add(actor='drp', cmdStr='processDotRoach')

            self.add(actor='fps',
                     cmdStr=f'cobraMoveSteps {motor}', stepsize=stepSize,
                     maskFile=os.path.join(maskFilesRoot, f'iter{iterNum}.csv'))

        # turning drp processing off
        self.tail.add(actor='drp', cmdStr='stopDotRoach')


class DotCrossing(FpsSequence):
    """ fps MoveToPfsDesign command. """
    seqtype = 'dotCrossing'
    dependencies = ['mcs']

    def __init__(self, visit, stepSize, count, exptime, doTest=False, **kwargs):
        FpsSequence.__init__(self, **kwargs)

        # turning on the illuminators
        self.add(actor='sps', cmdStr='bia on')
        self.add(actor='mcs', cmdStr='expose object',
                 exptime=exptime, frameId=visit.nextFrameId(), doFibreId=True)

        for iterNum in range(count):
            self.add(actor='fps', cmdStr=f'cobraMoveSteps {self.motor}', stepsize=stepSize)
            self.add(actor='mcs', cmdStr='expose object',
                     exptime=exptime, frameId=visit.nextFrameId(), doFibreId=True)

        # turning off the illuminators
        self.tail.add(actor='sps', cmdStr='bia off')


class PhiCrossing(DotCrossing):
    motor = 'phi'
    seqtype = 'phiCrossing'


class ThetaCrossing(DotCrossing):
    motor = 'theta'
    seqtype = 'thetaCrossing'
