"""A thetaPhiScan angle run step by step, stopped by a failure and resumed with thetaPhiScan continue."""
import types

import pytest

import ics.iicActor.Commands.MiscCmd as miscCmdModule
import ics.iicActor.sequenceList.fps as fpsSequenceList
import ics.iicActor.sequenceList.sps.calib as calib
from ics.iicActor.utils.sequenceStatus import Flag

CONFIG = dict(thetaPhiScan=dict(scienceTrace=dict(exptime=20, idDict=dict(arm='b,r')),
                                phiAngles=[25, 55, 85],
                                thetaAngles=[20, 50, 80],
                                scanPhiHome=True,
                                scanThetaHome=True,
                                moveToPfsDesign=dict(exptime=4.8, nIteration=6, tolerance=0.1)),
              mcs=dict(exptime=4.8),
              illuminators=dict(fidsOn='on'))


class CmdKeys(dict):
    """Parsed command keywords, as opscore hands them over: name -> object with `values`."""

    def __init__(self, **keywords):
        super().__init__({name: types.SimpleNamespace(values=values) for name, values in keywords.items()})


class Cmd:
    """A user command recording its replies."""

    def __init__(self, **keywords):
        self.cmd = types.SimpleNamespace(keywords=CmdKeys(**keywords))
        self.replies = []
        self.alive = True

    def inform(self, text):
        self.replies.append(('i', text))

    def warn(self, text):
        self.replies.append(('w', text))

    def fail(self, text):
        self.replies.append(('f', text))
        self.alive = False

    def finish(self, text=''):
        self.replies.append((':', text))
        self.alive = False

    @property
    def didFail(self):
        return any(code == 'f' for code, __ in self.replies)


class Step:
    """A cobra move or a scienceTrace, as the engine runs it."""

    def __init__(self, kind, **kwargs):
        self.kind = kind
        self.kwargs = kwargs
        self.status = types.SimpleNamespace(flag=Flag.INIT)

    def label(self, designNames):
        """'trace <comments>', or the kind of move and the name of the design it goes to."""
        if self.kind == 'trace':
            return f'trace {self.kwargs["comments"]}'
        return f'{self.kind} {designNames[self.kwargs["designId"]]}'


@pytest.fixture
def scan(monkeypatch):
    """A MiscCmd whose fps, engine and sequences are fakes; `scan.done` lists the steps run, in order.

    Each fps design gets a designId from its name; `scan.failOn` holds step labels to fail, once each.
    A failed step fails the user command unless it is run with failCmd=False, as the iic engine does.
    """
    done = []
    failOn = set()
    designs = {}

    def run(cmd, sequence, doFinish=True, failCmd=True):
        label = sequence.label({designId: name for name, designId in designs.items()})
        failed = label in failOn
        failOn.discard(label)
        sequence.status.flag = Flag.FAILED if failed else Flag.FINISHED
        done.append(label + (' FAILED' if failed else ''))
        if failed:
            (cmd.fail if failCmd else cmd.warn)(f'text="{label} failed"')

    def callFps(cmd, cmdStr, timeLim, failCmd=True):
        name = dict(arg.split('=') for arg in cmdStr.split() if '=' in arg)['designName']
        designId = designs.setdefault(name, len(designs) + 1)
        done.append(f'fps {cmdStr} -> 0x{designId:x}')
        keyword = types.SimpleNamespace(name='fpsDesignId', values=[f'0x{designId:x}'])
        return types.SimpleNamespace(replyList=[types.SimpleNamespace(keywords=[keyword])])

    opdb = types.SimpleNamespace(latestThetaPhiScanId=lambda: 1246,
                                 getScannedPhiFromThetaPhiScanId=lambda groupId, thetaAngles: [],
                                 getScannedThetaFromThetaPhiScanId=lambda groupId, phiAngles: [])
    actor = types.SimpleNamespace(actorConfig=CONFIG,
                                  engine=types.SimpleNamespace(run=run, opdb=opdb),
                                  spsConfig=types.SimpleNamespace(keysToCam=lambda cmdKeys, configDict=None: ['b1']),
                                  declareFpsDesign=lambda cmd, designId=None: None)

    monkeypatch.setattr(calib, 'ScienceTrace',
                        lambda cams, lampsKeys, duplicate, windowKeys, **kwargs: Step('trace', **kwargs))
    monkeypatch.setattr(fpsSequenceList, 'MoveToHome', lambda **kwargs: Step('home', **kwargs))
    monkeypatch.setattr(fpsSequenceList, 'MoveToPfsDesign', lambda **kwargs: Step('move', **kwargs))

    misc = miscCmdModule.MiscCmd(actor)
    misc._callFps = callFps
    misc.declareHomeDesign = lambda cmd, doFinish=True: designs.setdefault('home all', len(designs) + 1)

    misc.done, misc.failOn, misc.designs = done, failOn, designs
    return misc


def takeNextPhi(scan, **keywords):
    cmd = Cmd(**keywords)
    scan._thetaPhiScanCommand(cmd, lambda cmd: scan._startThetaPhiScan(cmd, constantAxis='phi'))
    return cmd


def takeNextTheta(scan, **keywords):
    cmd = Cmd(**keywords)
    scan._thetaPhiScanCommand(cmd, lambda cmd: scan._startThetaPhiScan(cmd, constantAxis='theta'))
    return cmd


def resume(scan):
    cmd = Cmd()
    scan._thetaPhiScanCommand(cmd, scan._continueThetaPhiScan)
    return cmd


def traces(scan):
    return [step for step in scan.done if step.startswith('trace')]


def test_fullScanOrder(scan):
    """Home all and cobraHome, then each theta angle, theta home after the first, moved to then traced."""
    cmd = takeNextPhi(scan, phiAngle=[55])
    assert not cmd.didFail, cmd.replies
    assert traces(scan) == ['trace cobraHome', 'trace thetaPhiScan_020_055', 'trace thetaPhiScan_home_055',
                            'trace thetaPhiScan_050_055', 'trace thetaPhiScan_080_055']
    assert scan.thetaPhiScanRun.isDone
    assert cmd.replies[-1] == (':', 'nRemainingPhis=3')


def test_unconfiguredAngleIsRejected(scan):
    cmd = takeNextPhi(scan, phiAngle=[10])
    assert cmd.didFail and 'not one of the configured phi angles (25,55,85)' in cmd.replies[-1][1], cmd.replies
    assert scan.done == [] and scan.thetaPhiScanRun is None


def test_continueResumesAtTheFailedTrace(scan):
    """The failed angle is moved to again and traced; nothing traced before is redone."""
    scan.failOn.add('trace thetaPhiScan_050_055')
    cmd = takeNextPhi(scan, phiAngle=[55])
    assert cmd.didFail and 'iic thetaPhiScan continue resumes here' in cmd.replies[-1][1], cmd.replies
    assert '2/4 theta angles traced' in cmd.replies[-1][1]
    nDone = len(scan.done)

    cmd = resume(scan)
    assert not cmd.didFail, cmd.replies
    design050 = scan.designs['thetaPhiScan_050_055']
    assert scan.done[nDone:] == [
        f'fps createThetaPhiScanDesign thetaAngle=50 phiAngle=55 designName=thetaPhiScan_050_055 -> 0x{design050:x}',
        'move thetaPhiScan_050_055', 'trace thetaPhiScan_050_055',
        'fps createThetaPhiScanDesign thetaAngle=80 phiAngle=55 designName=thetaPhiScan_080_055 -> 0x'
        f'{scan.designs["thetaPhiScan_080_055"]:x}',
        'move thetaPhiScan_080_055', 'trace thetaPhiScan_080_055']
    assert scan.thetaPhiScanRun.isDone


def test_continueAfterAFailedMove(scan):
    scan.failOn.add('move thetaPhiScan_020_025')
    cmd = takeNextPhi(scan, phiAngle=[25])
    assert cmd.didFail and 'cobra move to thetaPhiScan_020_025 not completed' in cmd.replies[-1][1], cmd.replies

    assert not resume(scan).didFail
    assert traces(scan) == ['trace cobraHome', 'trace thetaPhiScan_020_025', 'trace thetaPhiScan_home_025',
                            'trace thetaPhiScan_050_025', 'trace thetaPhiScan_080_025']


def test_continueBeforeTheCobraHomeTraceRedoesTheHoming(scan):
    scan.failOn.add('trace cobraHome')
    assert takeNextPhi(scan, phiAngle=[25]).didFail

    nDone = len(scan.done)
    assert not resume(scan).didFail
    assert scan.done[nDone:nDone + 2] == ['home home all', 'trace cobraHome']


def test_continueAtTheInnerHomeMovesBackToTheConstantAngleFirst(scan):
    """The inner axis alone goes home there, so the cobras are put back on the held angle before."""
    scan.failOn.add('trace thetaPhiScan_home_085')
    assert takeNextPhi(scan, phiAngle=[85]).didFail

    nDone = len(scan.done)
    cmd = resume(scan)
    assert not cmd.didFail, cmd.replies
    design020 = scan.designs['thetaPhiScan_020_085']
    designHome = scan.designs['thetaPhiScan_home_085']
    assert scan.done[nDone:nDone + 5] == [
        f'fps createThetaPhiScanDesign thetaAngle=20 phiAngle=85 designName=thetaPhiScan_020_085 -> 0x{design020:x}',
        'move thetaPhiScan_020_085',
        f'fps createHomeDesign theta designName=thetaPhiScan_home_085 -> 0x{designHome:x}',
        'home thetaPhiScan_home_085', 'trace thetaPhiScan_home_085']
    # Negative control: the angle before the inner home is not traced again.
    assert traces(scan).count('trace thetaPhiScan_020_085') == 1


def test_failedDesignCreationCanBeContinued(scan):
    calls = scan._callFps

    def failOnce(cmd, cmdStr, timeLim, failCmd=True):
        if 'thetaAngle=80' in cmdStr and not getattr(failOnce, 'failed', False):
            failOnce.failed = True
            return None
        return calls(cmd, cmdStr, timeLim, failCmd=failCmd)

    scan._callFps = failOnce
    cmd = takeNextPhi(scan, phiAngle=[25])
    assert cmd.didFail and 'fps createThetaPhiScanDesign thetaAngle=80' in cmd.replies[-1][1], cmd.replies

    assert not resume(scan).didFail
    assert traces(scan)[-1] == 'trace thetaPhiScan_080_025'


def test_nothingToContinue(scan):
    cmd = resume(scan)
    assert cmd.didFail and 'no thetaPhiScan to continue' in cmd.replies[-1][1]

    assert not takeNextPhi(scan, phiAngle=[25]).didFail
    cmd = resume(scan)
    assert cmd.didFail and 'nothing to continue' in cmd.replies[-1][1]


def test_aNewAngleReplacesAnUnfinishedOne(scan):
    scan.failOn.add('trace thetaPhiScan_050_025')
    assert takeNextPhi(scan, phiAngle=[25]).didFail

    cmd = takeNextPhi(scan, phiAngle=[55])
    assert ('w', 'text="replacing the unfinished thetaPhiScan groupId=1246 phiAngle=25: cobraHome traced, '
                 '2/4 theta angles traced"') in cmd.replies
    assert scan.thetaPhiScanRun.constantAngle == 55


def test_aSecondCommandIsRefusedWhileOneRuns(scan):
    scan.thetaPhiScanLock.acquire()
    try:
        cmd = resume(scan)
    finally:
        scan.thetaPhiScanLock.release()
    assert cmd.didFail and 'already running' in cmd.replies[-1][1]


def test_thetaScanResumesThroughItsPhiHome(scan):
    """takeNextTheta holds theta and steps phi, phi home after the first phi angle."""
    scan.failOn.add('trace thetaPhiScan_050_000')
    cmd = takeNextTheta(scan, thetaAngle=[50])
    assert cmd.didFail and 'iic thetaPhiScan continue resumes here' in cmd.replies[-1][1], cmd.replies

    nDone = len(scan.done)
    assert not resume(scan).didFail
    assert scan.done[nDone:nDone + 2] == [
        'fps createThetaPhiScanDesign thetaAngle=50 phiAngle=25 designName=thetaPhiScan_050_025 -> 0x'
        f'{scan.designs["thetaPhiScan_050_025"]:x}', 'move thetaPhiScan_050_025']
    assert traces(scan)[-3:] == ['trace thetaPhiScan_050_000', 'trace thetaPhiScan_050_055',
                                 'trace thetaPhiScan_050_085']
    assert 'fps createHomeDesign phi designName=thetaPhiScan_050_000' in ' '.join(scan.done)


def test_exceptionMidStepIsReportedAndCanBeContinued(scan):
    declare = scan.actor.declareFpsDesign

    def raiseOnce(cmd, designId=None):
        if not getattr(raiseOnce, 'raised', False):
            raiseOnce.raised = True
            raise RuntimeError('pfi is not connected, design will not declared as current.')
        return declare(cmd, designId=designId)

    scan.actor.declareFpsDesign = raiseOnce
    cmd = takeNextPhi(scan, phiAngle=[25])
    assert cmd.didFail, cmd.replies
    assert 'cobra move to thetaPhiScan_020_025 failed: pfi is not connected' in cmd.replies[-1][1]
    assert 'iic thetaPhiScan continue resumes here' in cmd.replies[-1][1]

    assert not resume(scan).didFail
    assert traces(scan)[-1] == 'trace thetaPhiScan_080_025'
