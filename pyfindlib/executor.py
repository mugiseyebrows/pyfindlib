import asyncio
import tempfile
import os
from .shared import adjust_command, eprint, debug_print, replace_many
import subprocess
import time
import sys

class ExecutorLogger:
    def __init__(self):
        self._data = []

    def log(self, cmd, stdout_name, stderr_name, returncode):
        self._data.append((cmd, stdout_name, stderr_name, returncode))
        #print("stdout_name, stderr_name", stdout_name, stderr_name)

    def flush(self, pstdout, pstderr):
        stdout_fd, stdout_name = tempfile.mkstemp(prefix='pyfind-exec-complete-', suffix='.stdout')
        stderr_fd, stderr_name = tempfile.mkstemp(prefix='pyfind-exec-complete-', suffix='.stderr')

        def write(fd, cmd_, data):
            #os.write(fd, cmd_)
            os.write(fd, data)
            #os.write(fd, b"\n")

        for item in self._data:
            cmd, input_stdout_name, input_stderr_name, returncode = item
            cmd_ = (" ".join(cmd) + "\n").encode('utf-8')
            with open(input_stdout_name, 'rb') as f:
                write(stdout_fd, cmd_, f.read())
            with open(input_stderr_name, 'rb') as f:
                write(stderr_fd, cmd_, f.read())
        os.close(stdout_fd)
        os.close(stderr_fd)
        if pstdout:
            with open(stdout_name, 'rb') as f:
                sys.stdout.buffer.write(f.read())
                sys.stdout.flush()
        else:
            eprint("stdout saved to {}".format(stdout_name))
        if pstderr:
            with open(stderr_name, 'rb') as f:
                sys.stderr.buffer.write(f.read())
                sys.stderr.flush()
        else:
            eprint("stderr saved to {}".format(stderr_name))

class Executor:
    def __init__(self, cdin: bool):
        self._cdin = cdin
    def exec(self, cmd: list[str], path: str):
        pass
    async def wait(self):
        pass

class SyncExecutor(Executor):

    def __init__(self, cdin: bool):
        super().__init__(cdin)

    def exec(self, cmd: list[str], path: str):
        cmd_ = adjust_command(cmd)
        cwd = None
        if self._cdin:
            if os.path.isdir(path):
                cwd = path
        debug_print("SyncExecutor.run", cmd_, "cwd", cwd)
        subprocess.run(cmd_, cwd=cwd)

def var_index(cmd):
    for i, e in enumerate(cmd):
        if '{' in e and '}' in e:
            return i
    return -1

def expand_var(var, paths) :
    res = []
    for path in paths:
        name = os.path.basename(path)
        basename, ext = os.path.splitext(name)
        dirname = os.path.dirname(path)
        transformed = replace_many(var, [
            ("{dirname}", dirname), 
            ("{basename}", basename),
            ("{ext}", ext),
            ("{name}", name),
            ("{path}", path),
            ("{}", path)
        ])
        res.append(transformed)
    return res

class XargsExecutor(Executor):
    def __init__(self, cmd, cdin):
        super().__init__(cdin)
        self._paths = []
        self._cmd = cmd
    
    def append(self, path):
        self._paths.append(path)

    async def wait(self):
        cmd = self._cmd
        ix = var_index(cmd)
        if ix > -1:
            cmd = cmd[:ix] + expand_var(cmd[ix], self._paths) + cmd[ix+1:]
            debug_print("cmd inserted", cmd)
        else:
            cmd = cmd + self._paths
            debug_print("cmd appended", cmd)
        cmd_ = adjust_command(cmd)
        subprocess.run(cmd_)

async def executor_worker(name, queue: asyncio.Queue, logger: ExecutorLogger):
    t0 = time.time()
    while True:
        debug_print(name, "waiting for new task")
        cmd, path, cdin = await queue.get()
        t1 = time.time()
        debug_print(name, "got task")
        
        stdout_fd, stdout_name = tempfile.mkstemp(prefix='pyfind-exec-', suffix='.stdout')
        stderr_fd, stderr_name = tempfile.mkstemp(prefix='pyfind-exec-', suffix='.stderr')

        cmd_ = adjust_command(cmd)
        cwd = None
        if cdin:
            if os.path.isdir(path):
                cwd = path

        debug_print(name, "running", cmd, "cwd", cwd)
        proc = await asyncio.subprocess.create_subprocess_exec(*cmd_, stdout=stdout_fd, stderr=stderr_fd, cwd=cwd)
        
        debug_print(name, "wait process to complete")
        await proc.wait()

        os.close(stdout_fd)
        os.close(stderr_fd)

        logger.log(cmd, stdout_name, stderr_name, proc.returncode)

        t2 = time.time()

        debug_print(name, "process completed, returncode", proc.returncode, "time", (t1 - t0), (t2 - t0))
        queue.task_done()

class AsyncExecutor(Executor):

    def __init__(self, conc: int = None, cdin: bool = False, pstdout: bool = False, pstderr: bool = False):
        super().__init__(cdin)
        queue = asyncio.Queue()
        if conc is None:
            conc = os.cpu_count()
        debug_print("create {} workers".format(conc))
        workers = []
        logger = ExecutorLogger()
        for i in range(conc):
            task = asyncio.create_task(executor_worker("worker {}".format(i), queue, logger))
            workers.append(task)
        self._queue = queue
        self._workers = workers
        self._conc = conc
        self._logger = logger
        self._pstdout = pstdout
        self._pstderr = pstderr
    
    def exec(self, cmd, path):
        self._queue.put_nowait((cmd, path, self._cdin))

    async def wait(self):
        queue = self._queue

        debug_print("join queue")
        await queue.join()
        debug_print("queue joined")

        debug_print("terminating workers")
        workers = self._workers
        for task in workers:
            task.cancel()
        asyncio.gather(*workers, return_exceptions=True)
        debug_print("workers terminated")

        self._logger.flush(self._pstdout, self._pstderr)
