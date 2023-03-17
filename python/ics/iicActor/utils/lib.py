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
