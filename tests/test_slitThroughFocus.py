"""iic slit throughfocus with pfilamps: the same lamp times at every slit position."""
import types

from ics.iicActor.sequenceList.sps.base import SlitThroughFocus


class CmdKeys(dict):
    """Parsed command keywords, as opscore hands them over: name -> object with `values`."""

    def __init__(self, **keywords):
        super().__init__({name: types.SimpleNamespace(values=values) for name, values in keywords.items()})


class LightSource(str):
    """A light source name with the lamps actor it drives."""
    lampsActor = 'pfilamps'


class Cam(str):
    """A camera name with the attributes a slit sequence reads from it."""

    def __new__(cls, name):
        cam = super().__new__(cls, name)
        cam.arm = name[0]
        cam.specName = f'sm{name[1]}'
        cam.lightSource = LightSource('pfi')
        return cam


def slitThroughFocus(poweredOff, **keywords):
    """iic slit throughfocus with these keywords on b1,r1, with the hexapods of `poweredOff` off."""
    cams = [Cam('b1'), Cam('r1')]
    keyRepo = types.SimpleNamespace(getNirTiming=lambda cams: dict(),
                                    getPoweredOffHexapods=lambda cams: poweredOff,
                                    deferHexapodsOff=lambda specNames: None,
                                    popDeferredHexapodsOff=lambda cams: set())
    iicActor = types.SimpleNamespace(spsConfig=types.SimpleNamespace(keysToCam=lambda cmdKeys, configDict=None: cams),
                                     engine=types.SimpleNamespace(keyRepo=keyRepo),
                                     actorConfig=dict(slit=dict(keepHexapodOn=False, fullInit=True)))
    return SlitThroughFocus.fromCmdKeys(iicActor, CmdKeys(**keywords))


def cmdStrs(cmdList):
    return [f'{subCmd.actor} {subCmd.cmdStr}' for subCmd in cmdList]


def test_slitThroughFocus():
    """Hexapod started and homed, the same arc at each focus, then homed and powered back off."""
    sequence = slitThroughFocus(['sm1'], neon=[5.0], position=[-1.0, 1.0, 3])
    assert sequence.seqtype == 'slitThroughFocus'

    exposures = []
    for focus in ['-1.0', '0.0', '1.0']:
        exposures += [f'sps slit focus={focus} abs cams=b1,r1', 'sps checkReady arc cams=b1,r1',
                      'pfilamps prepare neon=5', 'sps expose arc exptime=5 cams=b1,r1 doLamps isLast']
    assert cmdStrs(sequence) == ['sps slit start cams=b1,r1 fullInit', 'sps slit home cams=b1,r1'] + exposures
    assert cmdStrs(sequence.tail) == ['pfilamps stop', 'sps slit home cams=b1,r1', 'sps slit stop specNums=1']


def test_hexapodAlreadyOnStaysOn():
    # Negative control: a hexapod found powered on is homed but not powered off.
    sequence = slitThroughFocus([], neon=[5.0], position=[-1.0, 1.0, 3])
    assert cmdStrs(sequence.tail) == ['pfilamps stop', 'sps slit home cams=b1,r1']


def test_iisLampsAtEveryPosition():
    """IIS lamp times go to every arc of the scan, unscaled."""
    sequence = slitThroughFocus([], neon=[5.0], iisNeon=[3.0], position=[-1.0, 1.0, 3])
    assert cmdStrs(sequence).count('iis prepare neon=3') == 3, cmdStrs(sequence)
    assert all('doIIS' in cmdStr for cmdStr in cmdStrs(sequence) if cmdStr.startswith('sps expose')), cmdStrs(sequence)
