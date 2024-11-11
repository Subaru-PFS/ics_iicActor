import fysom
import ics.utils.time as pfsTime


class Flag(object):
    """Flag Describing the sequence conclusion."""
    INIT = -1
    FINISHED = 0
    FAILED = 1
    ABORTED = 2
    FINISHNOW = 3

    outputs = {INIT: '',
               FINISHED: 'complete',
               FAILED: '',
               ABORTED: 'abortRequested',
               FINISHNOW: 'finishRequested'}


class Status(fysom.Fysom):
    """Placeholder to handle iic_sequence status"""

    def __init__(self):
        self.flag = None
        self.output = None

        events = [{'name': 'init', 'src': 'none', 'dst': 'INIT'},
                  {'name': 'ready', 'src': 'INIT', 'dst': 'READY'},
                  {'name': 'execute', 'src': 'READY', 'dst': 'EXECUTING'},
                  {'name': 'fail', 'src': 'EXECUTING', 'dst': 'FAILED'},
                  {'name': 'finish', 'src': 'EXECUTING', 'dst': 'FINISHED'},
                  {'name': 'abort', 'src': 'EXECUTING', 'dst': 'ABORTED'},
                  {'name': 'amend', 'src': 'FINISHED', 'dst': 'READY'},
                  {'name': 'hardAmend', 'src': ['FINISHED', 'READY', 'FAILED'], 'dst': 'READY'}]

        fysom.Fysom.__init__(self, {'initial': 'none', 'events': events,
                                    'callbacks': {'on_INIT': self.reset, 'on_READY': self.reset}})
        self.init()

    def __str__(self):
        """for keywords."""
        return f'{self.current.lower()},"{self.output}"'

    @property
    def isActive(self):
        return self.current in ['READY', 'EXECUTING']

    @property
    def isAborted(self):
        return self.current == 'ABORTED'

    @property
    def isFlagged(self):
        return self.flag != Flag.INIT

    def reset(self, *args, **kwargs):
        """Initialize flag and output."""
        self.flag = Flag.INIT
        self.output = Flag.outputs[self.flag]

    def toOpDB(self):
        """for opdb."""
        return dict(status_flag=self.flag, cmd_output=self.output)

    def setFlag(self, flag, doWait=False):
        """Set status flag."""
        # don't change the flag, if sequence already concluded.
        if self.isFlagged:
            return

        self.flag = flag

        # wait until sequence is concluded, useful when called from another thread.
        while doWait and self.isActive:
            pfsTime.sleep.millisec()

    def conclude(self, failure=''):
        """Conclude the sequence, drive the state machine to either abort, finish or fail"""

        def getOutput(failure):
            # get default output.
            output = Flag.outputs[self.flag]
            # override if any failure.
            output = failure if failure else output
            return output

        # set flag and output correctly for opdb.
        self.setFlag(Flag.FAILED) if failure else self.setFlag(Flag.FINISHED)
        self.output = getOutput(failure)

        # at this point, we're in executing state, so trigger the correct state which match flag.
        if self.flag in [Flag.FINISHED, Flag.FINISHNOW]:
            self.finish()
        elif self.flag == Flag.FAILED:
            self.fail()
        elif self.flag == Flag.ABORTED:
            self.abort()
        else:
            raise KeyError(f'unknown flag :{self.flag}')
