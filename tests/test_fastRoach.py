"""iic fastRoach: one convergence of the cobras of a fresh black-dot design onto their dots."""
import types

import ics.iicActor.Commands.MiscCmd as miscCmdModule
import ics.iicActor.sequenceList.fps as fpsSequenceList

MOVE_TO_PFS_DESIGN = dict(exptime=4.8, nIteration=8, tolerance=0.005, noHome=False, twoStepsOff=False,
                          shortExpOff=False, noTweak=False, skipFiducialInterferenceCheck=False)
CONFIG = dict(moveToPfsDesign=MOVE_TO_PFS_DESIGN,
              fastRoach=dict(MOVE_TO_PFS_DESIGN, nIteration=10, noTweak=True, shortExpOff=True,
                             skipFiducialInterferenceCheck=True),
              illuminators=dict(doTurnOnIlluminator=False, cableBLampOn=False, useMcsBiaControl=True),
              maskFiles=dict(rootDir='/data/fps/maskFiles'))


class CmdKeys(dict):
    """Parsed command keywords, as opscore hands them over: name -> object with `values`."""

    def __init__(self, **keywords):
        super().__init__({name: types.SimpleNamespace(values=values) for name, values in keywords.items()})


class Cmd:
    """A user command recording its replies."""

    def __init__(self, **keywords):
        self.cmd = types.SimpleNamespace(keywords=CmdKeys(**keywords))
        self.replies = []

    def fail(self, text):
        self.replies.append(('f', text))


def fpsCommand(sequence):
    """The command string of the one fps subcommand of `sequence`."""
    [subCmd] = [subCmd for subCmd in sequence.cmdList if subCmd.actor == 'fps']
    return subCmd.cmdStr


def test_fastRoachConvergesWithItsOwnConfig():
    actor = types.SimpleNamespace(actorConfig=CONFIG)
    fastRoach = fpsSequenceList.FastRoach.fromCmdKeys(actor, CmdKeys(), designId=0x1234)
    assert fastRoach.seqtype == 'fastRoach'
    cmdStr = fpsCommand(fastRoach)
    assert cmdStr.startswith('moveToPfsDesign ') and f'designId={0x1234}' in cmdStr, cmdStr
    for key in ('iteration=10', 'tolerance=0.005', 'exptime=4.8', 'goHome', 'shortExpOff', 'noTweak',
                'skipFiducialInterferenceCheck'):
        assert key in cmdStr.split(), (key, cmdStr)
    assert 'twoStepsOff' not in cmdStr and 'maskFile' not in cmdStr, cmdStr

    # Negative control: a plain moveToPfsDesign keeps its own config.
    moveToPfsDesign = fpsSequenceList.MoveToPfsDesign.fromCmdKeys(actor, CmdKeys(), designId=0x1234)
    assert 'iteration=8' in fpsCommand(moveToPfsDesign).split()


def miscCmd(fpsReply):
    """A MiscCmd whose fps answers createBlackDotDesign with `fpsReply`; `misc.log` records what happens."""
    log = []

    def callFps(cmd, cmdStr, timeLim, failCmd=True):
        log.append(('fps', cmdStr))
        if fpsReply is None:
            cmd.fail('text="fps failed"')
            return None
        keyword = types.SimpleNamespace(name='fpsDesignId', values=[fpsReply])
        return types.SimpleNamespace(replyList=[types.SimpleNamespace(keywords=[keyword])])

    actor = types.SimpleNamespace(actorConfig=CONFIG,
                                  declareFpsDesign=lambda cmd, designId=None: log.append(('declare', designId)),
                                  engine=types.SimpleNamespace(
                                      run=lambda cmd, sequence, **kwargs: log.append(('run', sequence))))
    misc = miscCmdModule.MiscCmd(actor)
    misc._callFps = callFps
    misc.log = log
    return misc


def test_fastRoachOnEveryWorkingCobra():
    misc = miscCmd('0x00000000abcdef01')
    misc._fastRoach(Cmd())
    assert misc.log[:2] == [('fps', 'createBlackDotDesign'), ('declare', 0xabcdef01)]
    [(__, fastRoach)] = misc.log[2:]
    assert isinstance(fastRoach, fpsSequenceList.FastRoach)
    assert f'designId={0xabcdef01}' in fpsCommand(fastRoach)


def test_fastRoachOnAMaskFile():
    """The mask goes to the convergence too, else fps would move the cobras out of it onto their dots."""
    misc = miscCmd('0x00000000abcdef01')
    misc._fastRoach(Cmd(maskFile=['someCobras']))
    [maskArg] = [arg for arg in misc.log[0][1].split() if arg.startswith('maskFile=')]
    assert maskArg.startswith('maskFile=/data/fps/maskFiles/someCobras'), misc.log
    [(__, fastRoach)] = misc.log[2:]
    assert maskArg in fpsCommand(fastRoach).split(), (maskArg, fpsCommand(fastRoach))


def test_fastRoachWithoutItsConfig():
    """An iic config without a fastRoach section is refused before any design is made."""
    misc = miscCmd('0x00000000abcdef01')
    misc.actor.actorConfig = {k: v for k, v in CONFIG.items() if k != 'fastRoach'}
    cmd = Cmd()
    misc._fastRoach(cmd)
    assert misc.log == [] and 'no fastRoach section' in cmd.replies[-1][1], (misc.log, cmd.replies)


def test_fastRoachStopsWhenFpsCannotCreateTheDesign():
    misc = miscCmd(None)
    cmd = Cmd()
    misc._fastRoach(cmd)
    assert misc.log == [('fps', 'createBlackDotDesign')] and cmd.replies, (misc.log, cmd.replies)


def fullCommands(sequence):
    """'actor cmdStr' of the subcommands of `sequence`'s main list, in order."""
    return [f'{subCmd.actor} {subCmd.cmdStr}' for subCmd in sequence.cmdList]


def withFastRoach(**fastRoach):
    """CONFIG with these keys added to its fastRoach section."""
    return types.SimpleNamespace(actorConfig=dict(CONFIG, fastRoach=dict(CONFIG['fastRoach'], **fastRoach)))


def test_fastRoachPostFrame():
    """postFrame follows the convergence with fps measureBlindMove: one frame of where the cobras ended."""
    actor = types.SimpleNamespace(actorConfig=CONFIG)
    fastRoach = fpsSequenceList.FastRoach.fromCmdKeys(actor, CmdKeys(postFrame=[]), designId=0x1234)
    commands = fullCommands(fastRoach)
    assert len(commands) == 2 and commands[0].startswith('fps moveToPfsDesign '), commands
    assert commands[1] == 'fps measureBlindMove', commands


def test_fastRoachPostFrameFromConfig():
    """The iic config sets the default; the flag adds the frame whatever the config says."""
    for config, keys, expected in ((dict(postFrame=True), CmdKeys(), True),
                                   (dict(postFrame=False), CmdKeys(), False),
                                   (dict(postFrame=True), CmdKeys(postFrame=[]), True),
                                   (dict(postFrame=False), CmdKeys(postFrame=[]), True),
                                   (dict(), CmdKeys(), False)):
        fastRoach = fpsSequenceList.FastRoach.fromCmdKeys(withFastRoach(**config), keys, designId=0x1234)
        assert (fullCommands(fastRoach)[1:] == ['fps measureBlindMove']) is expected, (config, keys)


def test_fastRoachPostFrameBeforeTheIlluminatorsGoOff():
    """The frame closes the main list; the illuminators go off in the tail, after it."""
    illuminators = dict(CONFIG['illuminators'], doTurnOnIlluminator=True)
    actor = types.SimpleNamespace(actorConfig=dict(CONFIG, illuminators=illuminators))
    fastRoach = fpsSequenceList.FastRoach.fromCmdKeys(actor, CmdKeys(postFrame=[]), designId=0x1234)
    assert fullCommands(fastRoach)[-1] == 'fps measureBlindMove', fullCommands(fastRoach)
    assert [f'{subCmd.actor} {subCmd.cmdStr}' for subCmd in fastRoach.tail] == ['mcs biaControl off', 'peb led off']
