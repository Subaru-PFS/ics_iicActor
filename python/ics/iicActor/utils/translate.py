import numpy as np


def seqKeys(cmdKeys):
    """ Identify which spectrograph(cameras) is required to take data. """
    name = cmdKeys['name'].values[0] if 'name' in cmdKeys else ''
    comments = cmdKeys['comments'].values[0] if 'comments' in cmdKeys else ''
    doTest = 'doTest' in cmdKeys
    head = cmdKeys['head'].values if 'head' in cmdKeys else None
    tail = cmdKeys['tail'].values if 'tail' in cmdKeys else None
    groupId = cmdKeys['groupId'].values[0] if 'groupId' in cmdKeys else None
    return dict(name=name, comments=comments, doTest=doTest, head=head, tail=tail, groupId=groupId)


def identKeys(cmdKeys):
    """ Identify which spectrograph(cameras) is required to take data. """
    keys = dict()

    if 'cam' in cmdKeys and ('specNum' in cmdKeys or 'arm' in cmdKeys):
        raise RuntimeError('you cannot provide both cam and (specNum or arm)')

    for key in ['cam', 'arm', 'specNum']:
        # front end is singular, but sps is plural as its more consistent.
        tkey = f'{key}s'
        keys[tkey] = cmdKeys[key].values if key in cmdKeys else None

    return keys


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
    lampNames = 'halogen', 'hgcd', 'hgar', 'argon', 'neon', 'krypton', 'xenon'
    doShutterTiming = 'doShutterTiming' in cmdKeys
    timingOverHead = 5 if doShutterTiming else 0

    keys = {name: int(round(cmdKeys[name].values[0]) + timingOverHead) for name in lampNames if name in cmdKeys}

    if not keys:
        raise ValueError('no lamps has been specified')

    keys['shutterTiming'] = max(keys.values()) - timingOverHead if doShutterTiming else 0

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


def detThroughFocusKeys(cmdKeys):
    [start, stop, num] = cmdKeys['position'].values
    tilt = np.array(cmdKeys['tilt'].values) if 'tilt' in cmdKeys else np.zeros(3)
    positions = np.array([np.linspace(start, stop - np.max(tilt), num=int(num)), ] * 3).transpose() + tilt
    return positions.round(2)
