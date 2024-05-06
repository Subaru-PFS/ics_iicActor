import ics.utils.sps.lamps.utils.lampState as lampState
import numpy as np

seqArgs = '[<name>] [<comments>] [@doTest] [@noDeps] [<groupId>] [<head>] [<tail>]'


def seqKeys(cmdKeys):
    """ Identify which spectrograph(cameras) is required to take data. """
    name = cmdKeys['name'].values[0] if 'name' in cmdKeys else ''
    comments = cmdKeys['comments'].values[0] if 'comments' in cmdKeys else ''
    doTest = 'doTest' in cmdKeys
    head = cmdKeys['head'].values if 'head' in cmdKeys else None
    tail = cmdKeys['tail'].values if 'tail' in cmdKeys else None
    groupId = cmdKeys['groupId'].values[0] if 'groupId' in cmdKeys else None
    noDeps = 'noDeps' in cmdKeys
    return dict(name=name, comments=comments, doTest=doTest, noDeps=noDeps,
                head=head, tail=tail, groupId=groupId, cmdKeys=cmdKeys)


def spsExposureKeys(cmdKeys, doRaise=True):
    """ Identify which spectrograph(cameras) is required to take data. """

    if 'exptime' not in cmdKeys and doRaise:
        raise KeyError('exptime must be specified')

    exptime = cmdKeys['exptime'].values if 'exptime' in cmdKeys else None
    duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else 1
    return exptime, duplicate


def windowKeys(cmdKeys):
    """ Identify which spectrograph(cameras) is required to take data. """
    keys = dict()

    for key in ['window', 'blueWindow', 'redWindow']:
        if key in cmdKeys:
            keys[key] = cmdKeys[key].values

    return keys


def lampsKeys(cmdKeys):
    def toIisArg(name):
        return f'iis{name.capitalize()}'

    doShutterTiming = 'doShutterTiming' in cmdKeys
    overHead = 5 if doShutterTiming else 0

    keys = {name: int(round(cmdKeys[name].values[0]) + overHead) for name in lampState.allLamps if name in cmdKeys}
    iisKeys = {name: int(round(cmdKeys[toIisArg(name)].values[0]) + overHead) for name in lampState.allLamps if
               toIisArg(name) in cmdKeys}

    if not (keys or iisKeys):
        raise ValueError('no lamps has been specified')

    keys['shutterTiming'] = max(list(keys.values()) + list(iisKeys.values())) - overHead if doShutterTiming else 0
    keys['iis'] = iisKeys

    return keys


def dcbKeys(cmdKeys, forceHalogen=False):
    """"""
    switchOn = ','.join(cmdKeys['switchOn'].values) if 'switchOn' in cmdKeys else None
    switchOff = ','.join(cmdKeys['switchOff'].values) if 'switchOff' in cmdKeys else None
    # overriding if forceHalogen.
    switchOn = 'halogen' if forceHalogen and 'noLampCtl' not in cmdKeys else switchOn
    switchOff = 'halogen' if forceHalogen and 'switchOff' in cmdKeys else switchOff

    warmingTime = cmdKeys['warmingTime'].values[0] if 'warmingTime' in cmdKeys else None
    doForce = 'force' in cmdKeys

    timeLim = None if switchOn is None else 90
    timeLim = max(timeLim, warmingTime + 30) if warmingTime is not None else timeLim

    dcbOn = dict(on=switchOn, warmingTime=warmingTime, force=doForce, timeLim=timeLim)
    dcbOff = dict(off=switchOff)

    return dcbOn, dcbOff


def mcsExposureKeys(cmdKeys, actorConfig):
    mcsConfig = actorConfig['mcs']
    # setting mcs exptime consistently.
    exptime = cmdKeys['exptime'].values[0] if 'exptime' in cmdKeys else mcsConfig['exptime']
    return exptime


def ditheredFlatsKeys(cmdKeys):
    [start, stop, step] = cmdKeys['pixelRange'].values if 'pixelRange' in cmdKeys else [-6, 6, 0.3]
    nPositions = round((stop - start) / step + 1)
    positions = np.linspace(start, stop, nPositions).round(2)
    return positions


def fiberProfilesKeys(cmdKeys):
    [start, stop, step] = cmdKeys['pixelRange'].values if 'pixelRange' in cmdKeys else [-0.4, 0.4, 0.2]
    nPositions = round((stop - start) / step + 1)
    positions = np.linspace(start, stop, nPositions).round(2)
    return positions


def detThroughFocusKeys(cmdKeys):
    [start, stop, num] = cmdKeys['position'].values
    tilt = np.array(cmdKeys['tilt'].values) if 'tilt' in cmdKeys else np.zeros(3)
    positions = np.array([np.linspace(start, stop - np.max(tilt), num=int(num)), ] * 3).transpose() + tilt
    return positions.round(2)


def slitThroughFocusKeys(cmdKeys):
    [start, stop, num] = cmdKeys['position'].values
    positions = np.linspace(start, stop, int(num)).round(2)
    return positions
