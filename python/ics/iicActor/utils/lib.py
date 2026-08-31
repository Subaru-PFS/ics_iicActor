import ics.utils.cmd as cmdUtils


def makeCmdStr(cmd):
    """Reconstruct cmdStr stripping name and comments fields."""
    return f"iic {stripQuotes(cmdUtils.stripCmdKey(cmdUtils.stripCmdKey(cmd.rawCmd, 'name'), 'comments'))}"


def stripQuotes(txt):
    """ Strip quotes from string """
    return txt.replace('"', "'").strip()


def identSpecNums(cmdStr):
    """Identify specNums from cmdStr."""

    def findCmdKeyValue(key):
        values = cmdUtils.findCmdKeyValue(cmdStr, key)
        values = values if not values else [v.strip() for v in values.split(',')]
        return values

    specNums = findCmdKeyValue('specNums')
    cams = findCmdKeyValue('cams')
    # its either one or the other, cannot be both.
    specNums = specNums if not cams else [int(cam[1]) for cam in cams]

    return specNums


def thetaPhiScanDesignName(thetaAngle, phiAngle, atHome=None):
    """Name a thetaPhiScan step from its theta and phi angles, in degrees.

    atHome names the axis parked at its hard stop, or None when both angles are
    commanded. Theta at its hard stop points along tht1, which differs for every
    cobra, so no absolute angle describes it and it is named 'home'. Phi at its
    hard stop is 0 deg and keeps its number.
    """
    if atHome == 'theta':
        return f'thetaPhiScan_home_{phiAngle:03d}'

    return f'thetaPhiScan_{thetaAngle:03d}_{phiAngle:03d}'
