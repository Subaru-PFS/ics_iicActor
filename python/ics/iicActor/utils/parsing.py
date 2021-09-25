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
