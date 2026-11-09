"""The frames a boresight loop hands to fps calculateBoresight."""
import types

from ics.iicActor.sequenceList.fps import BoresightLoop
from ics.iicActor.utils.subcmd import CmdRet, SubCmd


def subCmd(actor, cmdStr, status):
    """A subcommand that ran with `status`: 0 succeeded, 1 failed, 2 cancelled, -1 not called."""
    cmd = SubCmd(sequence=None, actor=actor, cmdStr=cmdStr)
    cmd.cmdRet = CmdRet(status, [''], '')
    return cmd


def test_frameIdsAreTheSuccessfulExposures():
    """A failed or cancelled exposure, and any other command, leave no frame to reduce."""
    loop = types.SimpleNamespace(cmdList=[
        subCmd('mcs', 'biaControl on', 0),
        subCmd('mcs', 'expose object exptime=4.8 frameId=15395100 doFibreId', 0),
        subCmd('mcs', 'expose object exptime=4.8 frameId=15395101 doFibreId', 1),
        subCmd('mcs', 'expose object exptime=4.8 frameId=15395102 doFibreId', 2),
        subCmd('mcs', 'expose object exptime=4.8 frameId=15395103 doFibreId', 0),
        subCmd('fps', 'calculateBoresight frameIds=15395100,15395103 writeToDB', -1),
    ])
    assert BoresightLoop.frameIds.fget(loop) == [15395100, 15395103]


def test_reduceCommand():
    """The frames go to fps as a list, with the measurement written to opdb."""
    sent = []
    loop = types.SimpleNamespace(append=lambda actor, cmdStr, **kwargs: sent.append(
        SubCmd(None, actor, cmdStr, **kwargs).fullCmd))
    BoresightLoop.addReduce(loop, [15395100, 15395103])
    assert sent == ['fps calculateBoresight frameIds=15395100,15395103 writeToDB']
