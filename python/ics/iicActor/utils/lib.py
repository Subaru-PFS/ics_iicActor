import re
import time
from functools import partial, wraps


def genIdentKeys(cmdKeys):
    """ Identify which spectrograph(cameras) is required to take data. """
    keys = dict()
    if 'cam' in cmdKeys and ('sm' in cmdKeys or 'arm' in cmdKeys):
        raise RuntimeError('you cannot provide both cam and (sm or arm)')

    for key in ['cam', 'arm', 'sm']:
        # to be removed later on
        tkey = 'cams' if key == 'cam' else key
        keys[tkey] = cmdKeys[key].values if key in cmdKeys else None

    return keys

def genSequenceKwargs(cmd, customMade=False):
    cmdKeys = cmd.cmd.keywords
    head = cmdKeys['head'].values if 'head' in cmdKeys else None
    tail = cmdKeys['tail'].values if 'tail' in cmdKeys else None

    if not customMade and (head is not None or tail is not None):
        cmd.warn('text="not parsing head or tail here, sorry...')
        head = None
        tail = None

    name = cmdKeys['name'].values[0] if 'name' in cmdKeys else ''
    comments = cmdKeys['comments'].values[0] if 'comments' in cmdKeys else ''
    doTest = 'doTest' in cmdKeys

    return dict(name=name, comments=comments, head=head, tail=tail, doTest=doTest)


def stripQuotes(txt):
    """ Strip quotes from string """
    return txt.replace('"', "'").strip()


def stripField(rawCmd, field):
    """ Strip given text field from rawCmd """
    if re.search(field, rawCmd) is None:
        return rawCmd
    idlm = re.search(field, rawCmd).span(0)[-1]
    sub = rawCmd[idlm:]
    sub = sub if sub.find(' ') == -1 else sub[:sub.find(' ')]
    pattern = f' {field}{sub[0]}(.*?){sub[0]}' if sub[0] in ['"', "'"] else f' {field}{sub}'
    m = re.search(pattern, rawCmd)
    return rawCmd.replace(m.group(), '').strip()


def putMsg(func):
    @wraps(func)
    def wrapper(self, cmd, *args, **kwargs):
        self.start()
        self.putMsg(partial(func, self, cmd, *args, **kwargs))

    return wrapper


def threaded(func):
    @wraps(func)
    @putMsg
    def wrapper(self, cmd, *args, **kwargs):
        try:
            return func(self, cmd, *args, **kwargs)
        except Exception as e:
            cmd.fail('text=%s' % self.actor.strTraceback(e))

    return wrapper


def wait(ti=0.01):
    time.sleep(ti)
