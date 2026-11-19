"""iic moveToPfsDesign targetMaskFile: passed to fps as a maskFile path."""
import types

import pytest

import ics.iicActor.sequenceList.fps as fpsSequenceList

MOVE_TO_PFS_DESIGN = dict(exptime=4.8, nIteration=8, tolerance=0.005, noHome=False, twoStepsOff=False,
                          shortExpOff=False, noTweak=False, skipFiducialInterferenceCheck=False)
CONFIG = dict(moveToPfsDesign=MOVE_TO_PFS_DESIGN,
              illuminators=dict(doTurnOnIlluminator=False, cableBLampOn=False, useMcsBiaControl=True),
              maskFiles=dict(rootDir='/data/fps/maskFiles'))


class CmdKeys(dict):
    """Parsed command keywords, as opscore hands them over: name -> object with `values`."""

    def __init__(self, **keywords):
        super().__init__({name: types.SimpleNamespace(values=values) for name, values in keywords.items()})


def fpsCommand(cmdKeys):
    """The fps command string of an iic moveToPfsDesign given `cmdKeys`."""
    actor = types.SimpleNamespace(actorConfig=CONFIG)
    sequence = fpsSequenceList.MoveToPfsDesign.fromCmdKeys(actor, cmdKeys, designId=0x1234)
    [subCmd] = [subCmd for subCmd in sequence.cmdList if subCmd.actor == 'fps']
    return subCmd.cmdStr


def test_targetMaskFileGoesToFps(monkeypatch):
    monkeypatch.setattr(fpsSequenceList.os.path, 'isfile', lambda path: True)
    cmdStr = fpsCommand(CmdKeys(targetMaskFile=['MOD4_group1']))
    assert 'targetMaskFile=/data/fps/maskFiles/MOD4_group1.csv' in cmdStr.split(), cmdStr
    assert 'maskFile=' not in cmdStr.replace('targetMaskFile=', ''), cmdStr


def test_noTargetMaskFile():
    cmdStr = fpsCommand(CmdKeys())
    assert cmdStr.startswith('moveToPfsDesign ') and 'MaskFile' not in cmdStr, cmdStr


def test_missingTargetMaskFile(monkeypatch):
    monkeypatch.setattr(fpsSequenceList.os.path, 'isfile', lambda path: False)
    with pytest.raises(ValueError, match='MOD4_group9.csv does not exist'):
        fpsCommand(CmdKeys(targetMaskFile=['MOD4_group9']))
