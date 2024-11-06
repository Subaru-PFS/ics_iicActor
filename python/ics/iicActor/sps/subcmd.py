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
