from ics.iicActor.sps.subcmd import DcbCmd, SpsExpose
from ics.iicActor.utils.sequencing import Sequence
from ics.iicActor.utils.subcmd import SubCmd


class SpsSequence(Sequence):
    """Capture SpS sequence specificities here..."""
    lightBeam = True
    shutterRequired = True
    doCheckFocus = False

    def __init__(self, *args, **kwargs):
        Sequence.__init__(self, *args, **kwargs)

    @property
    def exposable(self):
        try:
            cams = self.job.actor.models['sps'].keyVarDict['exposable'].getValue()
        except:
            return None

        return ','.join(cams)

    def expose(self, exptype, exptime=0.0, duplicate=1, doTest=False, **identKeys):
        """ Append duplicate * sps expose to sequence """
        exptime = [exptime] if not isinstance(exptime, list) else exptime

        for expTime in exptime:
            for i in range(duplicate):
                self.append(SpsExpose.specify(exptype, expTime, doTest=doTest, **identKeys))

    def guessType(self, actor, cmdStr):
        """ Guess SubCmd type """
        if actor == 'dcb':
            cls = DcbCmd
        elif actor == 'sps' and 'expose' in cmdStr:
            cls = SpsExpose
        else:
            cls = SubCmd

        return cls

    def guessTimeLim(self, cmdStr, timeLim=0):
        """ Guess timeLim """
        keys = ['warmingTime', 'exptime']
        offset = 120 if 'rexm' in cmdStr else 0
        args = cmdStr.split(' ')
        for arg in args:
            for key in keys:
                try:
                    __, timeLim = arg.split(f'{key}=')
                except ValueError:
                    pass

        return int(float(timeLim)) + 60 + offset


class Loop(SpsSequence):
    def __init__(self, *args, **kwargs):
        SpsSequence.__init__(self, *args, **kwargs)

    def commandLogic(self, cmd):
        """ loop the command until being told to stop, store in database"""
        [subCmd] = self.cmdList
        self.processSubCmd(cmd, subCmd=subCmd)

        while not (self.doFinish or self.doAbort):
            self.archiveAndReset(cmd, subCmd)
            self.processSubCmd(cmd, subCmd=subCmd)

    def archiveAndReset(self, cmd, subCmd):
        """ archive a copy of the current command then reset it."""
        self.insert(subCmd.id, subCmd.copy())
        subCmd.initialise()
        subCmd.register(self, len(self.cmdList) - 1)
        subCmd.inform(cmd=cmd)
        self.sort(key=lambda x: x.id)
