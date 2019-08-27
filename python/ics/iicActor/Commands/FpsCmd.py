import opscore.protocols.keys as keys
import opscore.protocols.types as types
from opscore.utility.qstr import qstr

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
            ('startBoresightAcquisition', '', self.startBoresightAcquisition),
            ('addBoresightPosition', '', self.addBoresightPosition),
            ('reduceBoresightData', '', self.reduceBoresightData),
            ('abortBoresightAcquisition', '', self.abortBoresightAcquisition),

            ('fpsLoop', '[<expTime>] [<cnt>]', self.fpsLoop),
            # ('mcsLoop', '[<expTime>] [<cnt>] [@noCentroids]', self.mcsLoop),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("iic_iic", (1, 1),
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
            visit = self.actor.visitor.newVisit()
            fpsVisit = visit.visitId

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

        if self.boresightLoop is not None:
            cmd.fail('text="boresight loop already in progress"')
            return

        cmd.finish('')

    def abortBoresightAcquisition(self, cmd):
        """Abort a boresight acquisition loop. """

        if self.boresightLoop is None:
            cmd.fail('text="no boresight loop to abort"')
            return

        cmd.finish('')

    def addBoresightPosition(self, cmd):
        """Acquire data for a new boresight position. """

        if self.boresightLoop is None:
            cmd.fail('text="no boresight loop to add to"')
            return

        cmd.finish('')

    def reduceBoresightData(self, cmd):
        """Close out the current boresight acquisition loop and process the data. """

        if self.boresightLoop is None:
            cmd.fail('text="no boresight loop to reduce"')
            return

        cmd.finish('')
