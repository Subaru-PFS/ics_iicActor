import re
from functools import partial, wraps


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


def process(func):
    @wraps(func)
    @putMsg
    def wrapper(self, cmd, *args, **kwargs):
        try:
            return func(self, cmd, *args, **kwargs)
        except Exception as e:
            cmd.fail('text=%s' % self.actor.strTraceback(e))
        finally:
            self.isProcessed = True

    return wrapper
