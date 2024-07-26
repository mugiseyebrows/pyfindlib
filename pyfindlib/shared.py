import os
import datetime
import sys
import re
import glob

WIN_BUILTINS = ['echo', 'dir', 'type', 'copy', 'call', 'start']

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def print_utf8(s, end=b'\n', file=sys.stdout, flush = False):
    if not isinstance(end, bytes):
        end = end.encode('utf-8')
    file.buffer.write(s.encode('utf-8') + end)
    if flush:
        file.buffer.flush()

def _unc_path(path):
    return '\\\\?\\' + path

def _getsize(path, try_unc = True):
    try:
        size = os.path.getsize(path)
        return size
    except FileNotFoundError as e:
        if try_unc:
            path = _unc_path(path)
            return _getsize(path, False)
        else:
            eprint(e)

def _getctime(path, try_unc = True):
    try:
        ctime = os.path.getctime(path)
        return datetime.datetime.fromtimestamp(ctime)
    except FileNotFoundError as e:
        if try_unc:
            path = _unc_path(path)
            return _getctime(path, False)
        else:
            eprint(e)

def _getmtime(path, try_unc = True):
    try:
        mtime = os.path.getmtime(path)
        return datetime.datetime.fromtimestamp(mtime)
    except FileNotFoundError as e:
        if try_unc:
            path = _unc_path(path)
            return _getmtime(path, False)
        else:
            eprint(e)

def adjust_command(cmd):
    if sys.platform == 'win32':
        if cmd[0] in WIN_BUILTINS or re.match("^echo.$", cmd[0]):
            return ['cmd','/c'] + cmd
    return cmd

if os.environ.get('DEBUG_PYFINDLIB') == "1":
    debug_print = print
else:
    debug_print = lambda *args, **kwargs: None

def has_magic(path):
    # brackets in path is ambigous, plus in path is ambigous
    if os.path.exists(path):
        return False
    return glob.has_magic(path)

def glob_paths_dirs(paths):
    res = []
    for path in paths:
        if has_magic(path):
            for item in glob.glob(path):
                if os.path.isdir(item):
                    res.append(item)
        else:
            res.append(path)
    return res

def parse_size(arg):
    m = re.match('^([-+]?[0-9.e]+)+([cwbkmg]?)$', arg, re.IGNORECASE)
    if m is None:
        return None
    size = float(m.group(1))
    prefix = m.group(2)
    return int(size * {'k': 1024, 'm': 1024 * 1024, 'g': 1024 * 1024 * 1024, 'c': 1, 'b': 512, '': 1}[prefix.lower()])
