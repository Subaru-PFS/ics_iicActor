import ics.utils.cmd as cmdUtils
from ics.iicActor.utils.subcmd import SubCmd


class LampsCmd(SubCmd):
    """Handle lamp command specificities, ensuring lamp actor availability."""

    def __init__(self, sequence, actor, *args, **kwargs):
        if not sequence.lightSource.lampsActor:
            raise RuntimeError(f'Cannot control lampsActor for lightSource={sequence.lightSource}!')

        super().__init__(sequence, sequence.lightSource.lampsActor, *args, **kwargs)

    def abort(self, cmd):
        """Abort lamp warmup if active."""
        cmdVar = self.iicActor.cmdr.call(actor=self.actor, cmdStr='abort', forUserCmd=cmd, timeLim=10)
        if cmdVar.didFail:
            cmd.warn(cmdUtils.formatLastReply(cmdVar))


class DcbCmd(LampsCmd):
    def __init__(self, sequence, *args, **kwargs):
        if not sequence.lightSource.useDcbActor:
            raise RuntimeError('this command has been designed for dcb only')

        super().__init__(sequence, *args, **kwargs)


class ReleaseIlluminator(SubCmd):
    """Stop an illuminator lit for a whole run of exposures, unless the exposure meant to release it did.

    sps stops it when the last exposure of the run closes its shutters, so it is left alone once
    that exposure went through; any other end of the run sends stop.
    """

    def __init__(self, sequence, actor, lastExposure):
        super().__init__(sequence, actor, 'stop')
        self.lastExposure = lastExposure

    def callAndUpdate(self, cmd):
        """Stop the illuminator, unless the last exposure of its run went through."""
        if self.lastExposure.cmdRet.succeed:
            return

        super().callAndUpdate(cmd)
