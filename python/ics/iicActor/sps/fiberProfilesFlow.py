"""fiberProfiles across red resolutions, shared by the sps and dcb fiberProfiles commands."""
import ics.iicActor.sequenceList.sps.engineering as eng
from ics.iicActor.utils.sequenceStatus import Flag


def planRedResolutions(iicActor, cmd):
    """Red resolutions to take fiberProfiles in: the current one, then the other one unless skipOtherRedResolution.

    Parameters
    ----------
    iicActor : `iicActor`
    cmd : `actorcore.Command`

    Returns
    -------
    resolutions : `list` of `str`
        'low' or 'med', in run order.
    """
    cmdKeys = cmd.cmd.keywords
    cams = iicActor.spsConfig.keysToCam(cmdKeys)
    current = iicActor.engine.keyRepo.getCurrentRedResolution(cams)
    cmd.inform(f'text="RDA currently in {current} resolution mode"')

    resolutions = [current]
    if 'skipOtherRedResolution' not in cmdKeys:
        resolutions.append('med' if current == 'low' else 'low')

    return resolutions


def run(iicActor, cmd, FiberProfiles, resolutions):
    """Run one fiberProfiles sequence per red resolution, in order.

    The RDA is moved before a run in another resolution than the one it is in. Every run but the last is built with
    keepHexapodOn, deferring its hexapod power-off to the next one. The command fails at the first sequence that does
    not finish, and is concluded by the last run otherwise.

    Parameters
    ----------
    iicActor : `iicActor`
    cmd : `actorcore.Command`
    FiberProfiles : `type`
        fiberProfiles sequence class, built with ``fromCmdKeys(iicActor, cmdKeys, keepHexapodOn=...)``.
    resolutions : `list` of `str`
        Red resolutions, 'low' or 'med', in run order.
    """
    cmdKeys = cmd.cmd.keywords
    specNums = iicActor.spsConfig.keysToSpecNum(cmdKeys)
    cams = iicActor.spsConfig.keysToCam(cmdKeys)
    current = iicActor.engine.keyRepo.getCurrentRedResolution(cams)

    for iRun, resolution in enumerate(resolutions):
        isLast = iRun == len(resolutions) - 1

        if resolution != current:
            rdaMove = eng.RdaMove(specNums, resolution)
            iicActor.engine.run(cmd, rdaMove, doFinish=False)

            if rdaMove.status.flag != Flag.FINISHED:
                if cmd.alive:
                    cmd.fail('text="rdaMove not completed, stopping here."')
                return

            current = resolution

        fiberProfiles = FiberProfiles.fromCmdKeys(iicActor, cmdKeys, keepHexapodOn=not isLast)
        iicActor.engine.run(cmd, fiberProfiles, doFinish=isLast)

        if not isLast and fiberProfiles.status.flag != Flag.FINISHED:
            if cmd.alive:
                cmd.fail('text="fiberProfiles not completed, stopping here."')
            return
