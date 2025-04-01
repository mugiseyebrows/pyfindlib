import os
from .executor import AsyncExecutor, SyncExecutor, XargsExecutor
from .shared import eprint
import shutil
import datetime
from pathlib import Path
from .shared import _getmtime, _getsize, print_utf8, replace_many
import subprocess
import re
from .types import Exec
import sys
from collections import defaultdict

def cdup_path(path, cdup):
    for i in range(cdup):
        if '/' in path or '\\' in path:
            path = os.path.dirname(path)
        else:
            path = os.path.dirname(os.path.realpath(path))
    return path

class ActionBase:

    def __init__(self):
        self._cdup = None
        self._abspath = None
        self._queue = None
        self._count = 0

    def setOptions(self, cdup, abspath):
        self._cdup = cdup
        self._abspath = abspath

    def exec(self, root, name, path, is_dir):
        pass

    async def wait(self):
        pass

def tokens_to_cmd(tokens):
    def to_list(vs):
        if isinstance(vs, list):
            return vs
        return [vs]
    cmd = []
    for t in tokens:
        for e in to_list(t.cont):
            cmd.append(e)
    return cmd

def tokens_to_cmd_expand_vars(tokens, path):
    def to_list(vs):
        if isinstance(vs, list):
            return vs
        return [vs]
    cmd = []
    name = os.path.basename(path)
    basename, ext = os.path.splitext(name)
    dirname = os.path.dirname(path)
    for t in tokens:
        for e in to_list(t.cont):
            e = replace_many(e, [
                ("{dirname}", dirname), 
                ("{basename}", basename),
                ("{ext}", ext),
                ("{name}", name),
                ("{path}", path),
                ("{}", path)
            ])
            cmd.append(e)
    return cmd

class ActionExec(ActionBase):
    def __init__(self, tokens, async_: bool, conc: int, xargs: bool, cdin: bool, pstdout: bool, pstderr: bool):
        super().__init__()
        self._tokens = tokens
        self._paths = []

        if xargs:
            cmd = tokens_to_cmd(tokens)
            executor = XargsExecutor(cmd, cdin)
        else:
            if async_ or conc:
                executor = AsyncExecutor(conc, cdin, pstdout, pstderr)
            else:
                executor = SyncExecutor(cdin)
        self._executor = executor

    def exec(self, root, name, path, is_dir):

        path = cdup_path(path, self._cdup)

        if self._abspath:
            path = os.path.realpath(path)

        cmd = tokens_to_cmd_expand_vars(self._tokens, path)

        executor = self._executor

        if isinstance(executor, XargsExecutor):
            executor.append(path)
        else:
            executor.exec(cmd, path)

    async def wait(self):
        await self._executor.wait()

def _unc_path(path):
    return '\\\\?\\' + path

def _remove(path):
    try:
        os.remove(path)
    except FileNotFoundError:
        os.remove(_unc_path(path))

class ActionDelete(ActionBase):

    def exec(self, root, name, path, is_dir):
        path = cdup_path(path, self._cdup)
        if is_dir:
            eprint("Removing directory {}".format(path))
            shutil.rmtree(path)
        else:
            eprint("Removing file {}".format(path))
            _remove(path)

class ActionTouch(ActionBase):
    def exec(self, root, name, path, is_dir):
        path = cdup_path(path, self._cdup)
        Path(path).touch()

class Printer:
    def __init__(self, stat, trail, flush, basename):
        self._stat = stat
        self._f = None
        self._header = False
        self._trail = trail
        self._flush = flush
        self._basename = basename
    
    def print(self, path):
        path_ = path + ("\\" if self._trail and os.path.isdir(path) else "")
        if self._stat:
            mdate = _getmtime(path)
            if mdate:
                mdate_ = mdate.strftime("%Y-%m-%d %H:%M:%S")
            else:
                mdate_ = "????-??-?? ??:??:??"
            size = _getsize(path)
            text = "{} {:>16} {}".format(
                mdate_,
                size,
                path_
            )
        elif self._basename:
            text = os.path.basename(path)
        else:
            text = path_

        if self._stat and not self._header:
            text = "{:>19} {:>16} {}\n".format("mtime","size","path") + text
            self._header = True

        flush = self._flush
        try:
            print_utf8(text, flush=flush)
        except UnicodeEncodeError as e:
            print(e, flush=flush)

class ActionPrint(ActionBase):

    def __init__(self, stat, trail, flush, basename):
        super().__init__()
        self._printer = Printer(stat, trail, flush, basename)

    def exec(self, root, name, path, is_dir):
        path = cdup_path(path, self._cdup)

        if self._abspath:
            path_ = os.path.realpath(path)
        elif os.path.isabs(root):
            path_ = path
        else:
            path_ = os.path.relpath(path, os.getcwd())

        self._printer.print(path_)

class ActionGitStatus(ActionBase):
    
    def exec(self, root, name, path, is_dir):
        if not is_dir:
            return
        if not os.path.isdir(os.path.join(path, '.git')):
            return
        
        git = shutil.which('git')
        if git is None:
            git = 'C:\\Program Files\\Git\\cmd\\git.exe'
            if not os.path.isfile(git):
                raise ValueError("git not found")
            
        if self._abspath:
            path_ = os.path.realpath(path)
        elif os.path.isabs(root):
            path_ = path
        else:
            path_ = os.path.relpath(path, os.getcwd())

        lines = subprocess.check_output([git, 'status'], cwd=path).decode('utf-8').split('\n')

        (SEC_PRE, SEC_CHANGED, SEC_STAGED, SEC_UNMERGED, SEC_UNTRACKED) = range(5)

        sec = SEC_PRE
        
        not_staged = 0
        untracked = 0
        staged = 0
        unmerged = 0

        for line in lines:
            if line.startswith('Changes not staged for commit:'):
                sec = SEC_CHANGED
                continue
            if line.startswith('Untracked files:'):
                sec = SEC_UNTRACKED
                continue
            if line.startswith('Changes to be committed:'):
                sec = SEC_STAGED
                continue
            if line.startswith('Unmerged paths:'):
                sec = SEC_UNMERGED
                continue

            if sec == SEC_CHANGED:
                if re.match('\\s+(new file|modified|deleted)', line):
                    not_staged += 1
                    continue
            elif sec == SEC_UNTRACKED:
                if line.startswith('no changes added to commit'):
                    continue
                if line.strip() == '':
                    continue
                untracked += 1
            elif sec == SEC_UNMERGED:
                if line.strip() == '':
                    continue
                unmerged += 1
            elif sec == SEC_STAGED:
                if re.match('\\s+(new file|modified|deleted)', line):
                    staged += 1
                    continue


        print("{:>3} cha {:>3} sta {:>3} unm {:>3} unt   {}".format(not_staged, staged, unmerged, untracked, path_))
        



class ActionCallback(ActionBase):
    def __init__(self, callback: Exec):
        self._callback = callback

    def exec(self, root, name, path, is_dir):
        self._callback(root, name, path, is_dir)
    
def next_path(path):
    dir = os.path.dirname(path)
    name, ext = os.path.splitext(os.path.basename(path))
    i = 0
    while True:
        i += 1
        p = os.path.join(dir, name + "{:03d}".format(i) + ext)
        if not os.path.exists(p):
            return p

class ActionCopyOrMove(ActionBase):

    def __init__(self, copy: bool, dst: str, flat: bool, tree: bool, rename: bool, no_over: bool):
        self._copy = copy
        self._dst = dst
        if flat:
            self._flat = True
        elif tree:
            self._flat = False
        else:
            self._flat = False
        self._rename = rename
        self._no_over = no_over

    def exec(self, root, name, path, is_dir):
        # todo: dirs
        if is_dir:
            return
        
        if self._flat:
            file_dst = os.path.join(self._dst, name)
        else:
            file_dst = os.path.join(self._dst, os.path.relpath(path, root))

        if self._no_over and os.path.exists(file_dst):
            if os.path.getsize(path) == os.path.getsize(file_dst):
                return

        if self._rename and os.path.exists(file_dst):
            file_dst = next_path(file_dst)

        os.makedirs(os.path.dirname(file_dst), exist_ok=True)
        try:
            if self._copy:
                shutil.copy2(path, file_dst)
            else:
                shutil.move(path, file_dst)
            print("{} {} {}".format("copy" if self._copy else "move", path, file_dst), file=sys.stderr)
        except PermissionError as e:
            print(e, file=sys.stderr)

class ActionExtStat(ActionBase):

    def __init__(self):
        super().__init__()
        self._count = defaultdict(lambda: 0)
        self._size = defaultdict(lambda: 0)

    def exec(self, root, name, path, is_dir):
        if is_dir:
            return
        if '.' not in name:
            ext = ''
        else:
            ext = os.path.splitext(name)[1]
        self._count[ext] += 1
        self._size[ext] += os.path.getsize(path)
        return super().exec(root, name, path, is_dir)
    
    async def wait(self):
        await super().wait()
        size = [(ext, size) for ext, size in self._size.items()]
        size.sort(key=lambda item: item[1], reverse=True)
        print("{:<10} {:<10} {:<10}".format("ext","count","size"))
        for e, s in size:
            print("{:<10} {:<10} {:<10}".format(e,self._count[e],s))