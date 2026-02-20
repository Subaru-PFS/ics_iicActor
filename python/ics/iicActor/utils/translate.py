import os

import ics.utils.sps.lamps.utils.lampState as lampState
import numpy as np

seqArgs = '[<name>] [<comments>] [@doTest] [@noDeps] [@forceGrating] [@returnWhenShutterClose] [@skipBiaCheck] [@forcePfsConfig] [<groupId>] [<head>] [<tail>]'


def seqKeys(cmdKeys):
    """ Identify which spectrograph(cameras) is required to take data. """
    name = cmdKeys['name'].values[0] if 'name' in cmdKeys else ''
    comments = cmdKeys['comments'].values[0] if 'comments' in cmdKeys else ''
    doTest = 'doTest' in cmdKeys
    noDeps = 'noDeps' in cmdKeys
    forceGrating = 'forceGrating' in cmdKeys
    returnWhenShutterClose = 'returnWhenShutterClose' in cmdKeys
    skipBiaCheck = 'skipBiaCheck' in cmdKeys
    forcePfsConfig = 'forcePfsConfig' in cmdKeys
    head = cmdKeys['head'].values if 'head' in cmdKeys else None
    tail = cmdKeys['tail'].values if 'tail' in cmdKeys else None
    groupId = resolveGroupId(cmdKeys)

    return dict(name=name, comments=comments, doTest=doTest, noDeps=noDeps, forceGrating=forceGrating,
                returnWhenShutterClose=returnWhenShutterClose, skipBiaCheck=skipBiaCheck, forcePfsConfig=forcePfsConfig,
                head=head, tail=tail, groupId=groupId, cmdKeys=cmdKeys)


def resolveGroupId(cmdKeys):
    """Resolve groupId from command keys, supporting -1 as the latest."""
    groupId = int(cmdKeys['groupId'].values[0]) if 'groupId' in cmdKeys else None

    if groupId == -1:
        pass
    elif groupId is not None and groupId < 0:
        raise ValueError(f"Invalid groupId: {groupId}. Use -1 for latest or a non-negative integer (>= 0).")

    return groupId


def spsExposureKeys(cmdKeys, doRaise=True, defaultDuplicate=1):
    """ Identify which spectrograph(cameras) is required to take data. """

    if 'exptime' not in cmdKeys and doRaise:
        raise KeyError('exptime must be specified')

    exptime = cmdKeys['exptime'].values if 'exptime' in cmdKeys else None
    duplicate = cmdKeys['duplicate'].values[0] if 'duplicate' in cmdKeys else defaultDuplicate
    return exptime, duplicate


def windowKeys(cmdKeys, configDict=None):
    """Resolve window-related keys from cmdKeys first, then configDict."""
    keys = dict()

    for key in ['window', 'blueWindow', 'redWindow']:
        if key in cmdKeys:
            keys[key] = cmdKeys[key].values
        elif configDict and key in configDict:
            keys[key] = configDict[key]

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


def resolveKeys(cmdKeys, configDict, *keys, default=None):
    """Return dict of keys resolved from cmdKeys, then configDict, else default."""
    resolved = dict()

    for key in keys:
        if key in cmdKeys:
            values = cmdKeys[key].values
            if len(values)==0:
                values = True
            elif len(values)==1:
                values = values[0]
            resolved[key] = values

        elif configDict and key in configDict:
            resolved[key] = configDict[key]
        else:
            resolved[key] = default

    return resolved


def resolveKey(cmdKeys, configDict, key, default=None):
    """Return single key resolved from cmdKeys, then configDict, else default."""
    return resolveKeys(cmdKeys, configDict, key, default=default)[key]


def resolveAllKeys(cmdKeys, configDict, default=None):
    """Return dict resolving all configDict keys from cmdKeys, then configDict, else default."""
    if not configDict:
        return dict()
    return resolveKeys(cmdKeys, configDict, *configDict.keys(), default=default)


def resolveCmdConfig(cmdKeys, actorConfig, sectionName, default=None):
    """Return config section resolved from cmdKeys, then actorConfig[sectionName], else default."""
    configDict = actorConfig.get(sectionName, {})
    return resolveAllKeys(cmdKeys, configDict, default=default)


def resolveExptime(cmdKeys, configDict):
    """Return exptime resolved from command or configDict."""
    return resolveKey(cmdKeys, configDict, 'exptime')


def resolveMcsExptime(cmdKeys, actorConfig):
    """Return MCS exposure time resolved from command or actorConfig."""
    return resolveExptime(cmdKeys, actorConfig['mcs'])


def illuminatorKeys(actorConfig, requiredState=True):
    base = actorConfig['illuminators']
    illuminators = {**base,
                    'doTurnOnIlluminator': base['doTurnOnIlluminator'] and requiredState,
                    'cableBLampOn': base['cableBLampOn'] and requiredState}

    return illuminators


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


def constructMaskFilePath(maskFile, actorConfig):
    """
    Construct the file path for a given mask file.

    Parameters
    ----------
    maskFile : str
        Name of the mask file.
    actorConfig : dict
        Actor configuration dictionary.

    Returns
    -------
    str
        File path for the mask file.
    """
    return os.path.join(actorConfig['maskFiles']['rootDir'], f'{maskFile}.csv')


def getMaskFilePathFromCmd(cmdKeys, actorConfig):
    """
    Get the file path for the mask file from command-line arguments.

    Parameters
    ----------
    cmdKeys : dict
        Dictionary of command-line arguments.
    actorConfig : dict
        Actor configuration dictionary.

    Returns
    -------
    str
        File path for the mask file.
    """
    return constructMaskFilePath(cmdKeys['maskFile'].values[0], actorConfig) if 'maskFile' in cmdKeys else False


def getMaskFileArgsFromCmd(cmdKeys, actorConfig):
    """
    Get the command-line arguments for the mask file.

    Parameters
    ----------
    cmdKeys : dict
        Dictionary of command-line arguments.
    actorConfig : dict
        Actor configuration dictionary.

    Returns
    -------
    str
        Command-line arguments for the mask file.
    """
    maskFilePath = getMaskFilePathFromCmd(cmdKeys, actorConfig)
    maskFileArgs = f'maskFile={maskFilePath}' if maskFilePath else ''

    return maskFileArgs


def setDefaultComments(selectedArms):
    """
    Generate default comments based on the selected arms, ensuring the order
    is 'b', then 'm' or 'r', and finally 'n'.

    Parameters
    ----------
    selectedArms : set
        Set of arms selected, which may include 'b', 'r', 'm', and 'n'.

    Returns
    -------
    str
        A string representing the default comment based on the selected arms.
    """
    # Define the priority order for arms
    armOrder = ['b', 'r', 'm', 'n']
    # Sort the selected arms according to the desired order
    orderedArms = ''.join([arm for arm in armOrder if arm in selectedArms])

    # Construct the comment
    return f"{orderedArms} arm"
