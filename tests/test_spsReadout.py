"""How a windowed or row-binned readout reaches sps expose, and how the sequence is named."""
import types

import ics.iicActor.utils.translate as translate
from ics.iicActor.sequenceList.sps.base import Arcs
from ics.iicActor.sequenceList.sps.science import ScienceObject

CAMS = ['b1', 'r1']
MCS_EXPOSURE_BEFORE = dict(enabled=True, exptime=4.8, doFibreId=True, skipWindowed=True)


class CmdKeys(dict):
    """Parsed command keywords, as opscore hands them over: name -> object with `values`."""

    def __init__(self, **keywords):
        super().__init__({name: types.SimpleNamespace(values=values) for name, values in keywords.items()})


def scienceObject(**keywords):
    """iic scienceObject exptime=60 with these keywords, built as the command builds it."""
    actorConfig = dict(scienceExposure=dict(mcsExposureBefore=MCS_EXPOSURE_BEFORE))
    spsConfig = types.SimpleNamespace(keysToCam=lambda cmdKeys, configDict=None: CAMS)
    iicActor = types.SimpleNamespace(actorConfig=actorConfig, spsConfig=spsConfig)
    return ScienceObject.fromCmdKeys(iicActor, CmdKeys(exptime=[60.0], **keywords))


def spsExpose(sequence):
    """The one sps expose of `sequence`."""
    [subCmd] = [subCmd for subCmd in sequence if subCmd.cmdStr.startswith('expose')]
    return subCmd


def exposeCmd(sequence):
    """The command string of the one sps expose of `sequence`."""
    return spsExpose(sequence).cmdStr


def test_windowKeysResolveRowbin():
    assert translate.windowKeys(CmdKeys(rowbin=[25])) == dict(rowbin=25)
    # Negative control: what is not given is left out.
    assert translate.windowKeys(CmdKeys()) == dict()


def test_binnedScienceObject():
    """rowbin goes to sps expose, the sequence is _binned and skips the mcs exposure, as windowed does."""
    sequence = scienceObject(rowbin=[25])
    assert sequence.seqtype == 'scienceObject_binned'
    assert 'rowbin=25' in exposeCmd(sequence) and 'window' not in exposeCmd(sequence)
    assert not spsExpose(sequence).mcsExposureBefore['enabled']


def test_windowedScienceObject():
    sequence = scienceObject(window=[500, 1000])
    assert sequence.seqtype == 'scienceObject_windowed'
    assert 'window=500,1000' in exposeCmd(sequence) and 'rowbin' not in exposeCmd(sequence)


def test_fullFrameScienceObject():
    # Negative control: neither window nor rowbin, a full frame with its mcs exposure before.
    sequence = scienceObject()
    assert sequence.seqtype == 'scienceObject'
    assert 'rowbin' not in exposeCmd(sequence) and 'window' not in exposeCmd(sequence)
    assert spsExpose(sequence).mcsExposureBefore['enabled']


class LightSource(str):
    """A light source name with the lamps actor it drives."""
    lampsActor = 'pfilamps'


class Cam(str):
    """A camera name with the attributes a timed-lamps sequence reads from it."""

    def __new__(cls, name):
        cam = super().__new__(cls, name)
        cam.arm = name[0]
        cam.lightSource = LightSource('pfi')
        return cam


def arcs(**keywords):
    """iic expose arc neon=5 with these keywords, built as the command builds it."""
    cams = [Cam(name) for name in CAMS]
    spsConfig = types.SimpleNamespace(keysToCam=lambda cmdKeys, configDict=None: cams)
    keyRepo = types.SimpleNamespace(getNirTiming=lambda cams: dict())
    iicActor = types.SimpleNamespace(spsConfig=spsConfig, engine=types.SimpleNamespace(keyRepo=keyRepo))
    return Arcs.fromCmdKeys(iicActor, CmdKeys(neon=[5.0], **keywords))


def test_binnedArcs():
    sequence = arcs(rowbin=[25])
    assert sequence.seqtype == 'arcs_binned'
    assert 'rowbin=25' in exposeCmd(sequence) and 'window' not in exposeCmd(sequence)


def test_windowedArcs():
    sequence = arcs(blueWindow=[500, 1000])
    assert sequence.seqtype == 'arcs_windowed'
    assert 'blueWindow=500,1000' in exposeCmd(sequence) and 'rowbin' not in exposeCmd(sequence)


def test_fullFrameArcs():
    # Negative control: neither window nor rowbin.
    sequence = arcs()
    assert sequence.seqtype == 'arcs'
    assert 'rowbin' not in exposeCmd(sequence) and 'window' not in exposeCmd(sequence)
