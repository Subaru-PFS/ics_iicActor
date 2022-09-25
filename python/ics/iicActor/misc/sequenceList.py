import os

from ics.iicActor.fps.sequence import FpsSequence
from ics.iicActor.sps.timed import timedLampsSequence
from ics.iicActor.sps.sequence import SpsSequence


class NearDotConvergence(FpsSequence):
    seqtype = 'nearDotConvergence'
    dependencies = ['mcs']

    def __init__(self, designId, visitId, maxIteration, tolerance, maskFile=False, doTest=False, **kwargs):
        FpsSequence.__init__(self, **kwargs)
        # turning on the illuminators
        self.add(actor='peb', cmdStr='led on')
        self.add(actor='sps', cmdStr='bia on')

        # move cobras to home
        self.add(actor='fps', cmdStr='moveToHome all', visit=visitId, timeLim=300)

        # going to nearDot pfsDesign
        self.add(actor='fps', cmdStr='moveToPfsDesign', designId=designId, visit=visitId, iteration=maxIteration,
                 tolerance=tolerance, maskFile=maskFile, timeLim=300)

        # turning off the illuminators
        self.tail.add(actor='peb', cmdStr='led off')
        self.tail.add(actor='sps', cmdStr='bia off')


class DotRoach(SpsSequence):
    """ fps MoveToPfsDesign command. """
    seqtype = 'dotRoach'
    dependencies = ['fps']

    def __init__(self, visitId, maskFile, keepMoving, cams, rootDir, stepSize, count, motor, windowedFlat, doTest=False,
                 stepRatio=4, **kwargs):
        SpsSequence.__init__(self, **kwargs)

        dataRoot = os.path.join(rootDir, f'v{str(visitId).zfill(6)}')
        maskFilesRoot = os.path.join(dataRoot, 'maskFiles')

        # use sps erase command to niet things up.
        self.add(actor='sps', cmdStr='erase', cams=cams)

        # turning drp processing on
        self.add(actor='drp', cmdStr='startDotRoach', dataRoot=dataRoot, maskFile=maskFile, keepMoving=keepMoving)

        # exptime = dict(halogen=int(windowedFlat['exptime']), shutterTiming=False)
        exptime = float(windowedFlat['exptime'])
        redWindow = windowedFlat['redWindow']
        blueWindow = windowedFlat['blueWindow']

        # initial exposure
        self.expose(exptype='domeflat', exptime=exptime, cams=cams, doTest=doTest,
                    redWindow='%d,%d' % (redWindow['row0'], redWindow['nrows']),
                    blueWindow='%d,%d' % (blueWindow['row0'], blueWindow['nrows']))

        self.add(actor='drp', cmdStr='processDotRoach')

        for iterNum in range(count):
            self.add(actor='fps',
                     cmdStr=f'cobraMoveSteps {motor}', stepsize=stepSize,
                     maskFile=os.path.join(maskFilesRoot, f'iter{iterNum}.csv'))

            self.expose(exptype='domeflat', exptime=exptime, cams=cams, doTest=doTest,
                        redWindow='%d,%d' % (redWindow['row0'], redWindow['nrows']),
                        blueWindow='%d,%d' % (blueWindow['row0'], blueWindow['nrows']))

            self.add(actor='drp', cmdStr='processDotRoach')

        # dotRoach in the opposite direction.
        self.add(actor='drp', cmdStr='reverseDotRoach')
        stepSize = int(round(-stepSize / 4))

        for iterNum in range(2 * stepRatio):
            fileName = 'finalMove.csv' if not iterNum else f'iter{iterNum + count}.csv'
            self.add(actor='fps',
                     cmdStr=f'cobraMoveSteps {motor}', stepsize=stepSize,
                     maskFile=os.path.join(maskFilesRoot, fileName))

            self.expose(exptype='domeflat', exptime=exptime, cams=cams, doTest=doTest,
                        redWindow='%d,%d' % (redWindow['row0'], redWindow['nrows']),
                        blueWindow='%d,%d' % (blueWindow['row0'], blueWindow['nrows']))

            self.add(actor='drp', cmdStr='processDotRoach')

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
        self.add(actor='peb', cmdStr='led on')

        self.add(actor='mcs', cmdStr='expose object',
                 exptime=exptime, frameId=visit.nextFrameId(), doFibreId=True)

        for iterNum in range(count):
            self.add(actor='fps', cmdStr=f'cobraMoveSteps {self.motor}', stepsize=stepSize)
            self.add(actor='mcs', cmdStr='expose object',
                     exptime=exptime, frameId=visit.nextFrameId(), doFibreId=True)

        # turning off the illuminators
        self.tail.add(actor='sps', cmdStr='bia off')
        self.tail.add(actor='peb', cmdStr='led off')


class PhiCrossing(DotCrossing):
    motor = 'phi'
    seqtype = 'phiCrossing'


class ThetaCrossing(DotCrossing):
    motor = 'theta'
    seqtype = 'thetaCrossing'


class FastRoach(timedLampsSequence):
    """ fps MoveToPfsDesign command. """
    seqtype = 'dotRoach'
    dependencies = ['fps']

    def __init__(self, visitId, maskFile, cams, rootDir, stepSize, count, motor, windowedFlat, doTest=False,
                 **kwargs):
        timedLampsSequence.__init__(self, **kwargs)

        maskFilesRoot = '/data/dotRoach/fastRoach'

        exptime = dict(halogen=60, shutterTiming=False)

        for i in range(3):
            self.expose(exptype='flat', exptime=exptime, cams=cams, doTest=doTest)

        for iterNum in range(37):

            self.add(actor='fps',
                     cmdStr=f'cobraMoveSteps phi', stepsize=-40,
                     maskFile=os.path.join(maskFilesRoot, f'iter{iterNum}.csv'))

        for i in range(3):
            self.expose(exptype='flat', exptime=exptime, cams=cams, doTest=doTest)