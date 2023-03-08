class Status(object):
    """Placeholder to handle iic_sequence status"""

    def __init__(self, statusStr, statusFlag, output):
        self.statusStr = statusStr
        self.statusFlag = statusFlag
        self.output = output

    def __str__(self):
        """for keywords."""
        return f'{self.statusStr},"{self.output}"'

    @property
    def isActive(self):
        return self.statusStr == 'active'

    @property
    def isAborted(self):
        return self.statusStr == 'aborted'

    def toOpDB(self):
        """for opdb."""
        return dict(status_flag=self.statusFlag, cmd_output=self.output)

    @classmethod
    def factory(cls, status, output=''):
        if status in ['init', 'active']:
            return cls(status, -1, 'None')
        elif status == 'finish':
            return cls('finished', 0, 'complete')
        elif status == 'fail':
            return cls('failed', 1, output)
        elif status == 'abort':
            return cls('aborted', 2, 'abortRequested')
        elif status == 'finishNow':
            return cls('finished', 3, 'finishRequested')
        else:
            raise KeyError(f'unknown status {status}')
