from shortwalk import walk
import os
from .action import ActionBase
from .types import ExtraArgs

def walk_all(paths, pred, action: ActionBase, extraArgs: ExtraArgs):
    
    if extraArgs.first is not None:
        need_to_stop = lambda count: count >= extraArgs.first
    else:
        need_to_stop = lambda count: False

    executed = 0
    for path in paths:
        for root, dirs, files in walk(path, maxdepth=extraArgs.maxdepth, skip=extraArgs.skip):
            for name in dirs:
                p = os.path.join(root, name)
                if pred(name, p, True):
                    action.exec(path, name, p, True)
                    executed += 1
                    if need_to_stop(executed):
                        return
            for name in files:
                p = os.path.join(root, name)
                if pred(name, p, False):
                    action.exec(path, name, p, False)
                    executed += 1
                    if need_to_stop(executed):
                        return