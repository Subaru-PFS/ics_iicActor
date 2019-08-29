
import opscore.protocols.keys as keys
import opscore.protocols.types as types
from opscore.utility.qstr import qstr

from ics.iicActor import visit

class BoresightLoop(object):
    """The state required to run a boresight measurement loop.

    Basically, the Gen2 command knows about the telescope motion, and
    interleaves POPT2 rotations with requests to us to expose. At the
    end we are commanded to read the data and generate a new boresight.

    """
    def __init__(self, visit, expTime, nExposures):
        self.visit = visit
        self.expTime = expTime
        self.nExposures = nExposures
        self.frameId = 0

    @property
    def startFrame(self):
        return self.visit.visitId*100

    @property
    def endFrame(self):
        return self.visit.visitId*100 + self.frameId - 1

    def nextFrameId(self):
        frameId = self.frameId
        self.frameId += 1
        return self.visit.visitId*100 + frameId

class FpsCmd(object):

    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        self.boresightLoop = None

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('startBoresightAcquisition', '[<expTime>] [<nExposures>]',
             self.startBoresightAcquisition),
            ('addBoresightPosition', '', self.addBoresightPosition),
            ('reduceBoresightData', '', self.reduceBoresightData),
            ('abortBoresightAcquisition', '', self.abortBoresightAcquisition),

            ('fpsLoop', '[<expTime>] [<cnt>]', self.fpsLoop),
            # ('mcsLoop', '[<expTime>] [<cnt>] [@noCentroids]', self.mcsLoop),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("iic_iic", (1, 1),
                                        keys.Key("nPositions", types.Int(),
                                                 help="number of angles to measure at"),
                                        keys.Key("nExposures", types.Int(),
                                                 help="number of exposures to take at each position"),
                                        keys.Key("cnt", types.Int(),
                                                 default=1,
                                                 help="times to run loop"),
                                        keys.Key("id", types.Long(),
                                                 help="fpsDesignId for the field, "
                                                 "which defines the fiber positions"),
                                        keys.Key("expTime", types.Float(),
                                                 default=1.0,
                                                 help="Seconds for exposure"))

    def fpsLoop(self, cmd):
        """Run an MCS+FPS loop, without moving cobras. """

        cmdKeys = cmd.cmd.keywords
        expTime = cmdKeys['expTime'].values[0] \
                  if 'expTime' in cmdKeys \
                     else 1.0
        cnt = cmdKeys['cnt'].values[0] \
              if 'cnt' in cmdKeys \
                 else 1

        if cnt > 100:
            cmd.fail('text="cannot request more than 100 FPS images at once"')
            return

        try:
            ourVisit = self.actor.visitor.newVisit('fpsLoop')
        except visit.VisitActiveError:
            cmd.fail('text="IIC already has an active visit: %s"' % (self.actor.visitor.activeVisit))
            raise

        fpsVisit = ourVisit.visitId

        try:
            ret = self.actor.cmdr.call(actor='fps',
                                       cmdStr=f'testLoop cnt={cnt} expTime={expTime:0.2f} visit={fpsVisit}',
                                       timeLim=(5+expTime)*cnt)
            if ret.didFail:
                raise RuntimeError("FPS failed to run a testLoop!")
        finally:
            self.actor.visitor.releaseVisit()

        cmd.finish()

    def startBoresightAcquisition(self, cmd):
        """Start a boresight acquisition loop. """

        cmdKeys = cmd.cmd.keywords
        expTime = cmdKeys['expTime'].values[0] \
                  if 'expTime' in cmdKeys \
                     else 2.0
        nExposures = cmdKeys['nExposures'].values[0] \
              if 'nExposures' in cmdKeys \
                 else 2

        if self.boresightLoop is not None:
            cmd.fail('text="boresight loop already in progress"')
            return

        try:
            visit = self.actor.visitor.newVisit()
        except Exception as e:
            cmd.fail('text="failed to start boresight loop: %s"' % e)
            return

        self.boresightLoop = BoresightLoop(visit, expTime, nExposures)
        cmd.finish('text="Initialized boresight loop"')

    def addBoresightPosition(self, cmd):
        """Acquire data for a new boresight position. """

        if self.boresightLoop is None:
            cmd.fail('text="no boresight loop to add to"')
            return

        expTime = self.boresightLoop.expTime
        for i in range(self.boresightLoop.nExposures):
            try:
                frameId = self.boresightLoop.nextFrameId()
                cmd.inform('text="taking MCS exposure %d/%d"' % (i+1, self.boresightLoop.nExposures))
                ret = self.actor.cmdr.call(actor='mcs',
                                           cmdStr=f'expose object expTime={expTime:0.2f} frameId={frameId} ',
                                           timeLim=30+expTime)
                if ret.didFail:
                    raise RuntimeError("IIC failed to take a MCS exposure")
            except RuntimeError:
                cmd.fail('text="ICC failed to take an MCS exposure')
            except Exception as e:
                cmd.fail('text="ICC failed to take an MCS exposure: %s"' % (e))

        cmd.finish()

    def reduceBoresightData(self, cmd):
        """Close out the current boresight acquisition loop and process the data. """

        if self.boresightLoop is None:
            cmd.fail('text="no boresight loop to reduce"')
            return

        startFrame = self.boresightLoop.startFrame
        endFrame = self.boresightLoop.endFrame
        nFrames = endFrame - startFrame + 1

        try:
            if nFrames < 2:
                raise RuntimeError('not enough frames')

            cmd.inform('text="measuring MCS center from %d frames from %s"' % (nFrames, startFrame))
            ret = self.actor.cmdr.call(actor='fps',
                                       cmdStr=f'calculateBoresight startFrame={startFrame} endFrame={endFrame}',
                                       timeLim=30)
            if ret.didFail:
                raise RuntimeError("FPS failed to calculate a boresight")
        except RuntimeError as e:
            cmd.fail('text="failed to reduce boresight, closed loop: %s"' % (str(e)))
            return
        finally:
            self.boresightLoop = None
            self.actor.visitor.releaseVisit()

        cmd.finish('')

    def abortBoresightAcquisition(self, cmd):
        """Abort a boresight acquisition loop. """

        if self.boresightLoop is None:
            cmd.warn('text="no boresight loop to abort"')

        self.boresightLoop = None
        self.actor.visitor.releaseVisit()

        cmd.finish('text="boresight loop aborted"')
