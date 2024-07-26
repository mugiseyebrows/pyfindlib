import os
from shortwalk import walk
from bashrange import expand_args
import asyncio
from .parse import parse_args
from .node import expr_to_pred
from .alg import walk_all

"""
def to_int(v):
    if v is None:
        return v
    return int(v)

def to_int_or_zero(v):
    if v is None:
        return 0
    return int(v)

def first_truthy(*args):
    for arg in args:
        if arg:
            return arg


def group_tail(tokens):
    i = 0
    if len(tokens) < 1:
        return -1
    if tokens[i][0] == TOK.not_:
        i += 1
    if i > len(tokens):
        return -1
    if tokens[i][0] in tok_pred:
        i += 2
    if i > len(tokens):
        return -1
    if i == 0:
        return -1
    return i
"""

def print_help():
    print("""usage: pyfind [PATHS] [OPTIONS] [CONDITIONS] [-async] [-exec cmd args {} ;] [-delete] [-print]

finds files and dirs that satisfy conditions (predicates) and executes action

options:
  -maxdepth NUMBER     walk no deeper than NUMBER levels
  -output PATH         output to file instead of stdout
  -append              append to file instead of rewrite
  -abspath             print absolute paths
  -async               execute asyncronously (do not wait for termination)
  -conc NUMBER         concurrency limit for -async -exec, 
                       defaults to number of cpu cores
  -trail               print trailing slash on directories
  -cdup NUMBER         print (or perform action on) parent path (strip NUMBER 
                       trailing components from path)
  -first NUMBER        print (or perform action on) first NUMBER found items and stop
  -xargs               execute command once with all matched files as arguments

actions:
  -delete              delete matched file
  -exec                execute command(s)
  -print               print matched paths to output (default action)
  -stat                print matched paths with file size and modification date
  -touch               touch file (set mtime to current time)
  -gitstat             print git status summary

predicates:
  -mtime DAYS          if DAYS is negative: modified within DAYS days, 
                       if positive modified more than DAYS days ago
  -ctime DAYS          same as -mtime, but when modified metadata not content
  -mmin MINUTES        if MINUTES is negative: modified within MINUTES minutes, 
                       if positive modified more than MINUTES minutes ago
  -mdate DATE1 [DATE2] modified at DATE1 (or between DATE1 and DATE2)
  -cmin MINUTES        same as -mmin, but when modified metadata not content
  -newer PATH/TO/FILE  modified later than PATH/TO/FILE
  -newermt DATETIME    modified later than DATETIME
  -newerct DATETIME    same as -newermt but when modified metadata not content
  -name PATTERNS        filename matches PATTERN (wildcard)
  -iname PATTERNS       same as -name but case insensitive
  -path PATTERNS        file path matches PATTERN
  -ipath PATTERNS       same as -path but case insensitive
  -grep PATTERN        file content contains PATTERN
  -igrep PATTERN       same as -grep but case insensitive
  -bgrep PATTERN       same as -grep but PATTERN is binary expression
  -docgrep PATTERN     grep odt and ods files for PATTERN
  -type d              is directory
  -type f              is file
  -cpptmp              temporary cpp files (build artifacts - objects and generated code)
  -gitdir              directory with .git in it

predicates can be inverted using -not, can be grouped together in boolean expressions 
using -or and -and and parenthesis

binds:
  {}          path to file
  {path}      path to file
  {name}      name with extension
  {ext}       extension
  {basename}  name without extension
  {dirname}   directory name

examples:
  pyfind -iname *.py -mmin -10
  pyfind -iname *.cpp *.h -not ( -iname moc_* ui_* )
  pyfind -iname *.h -exec pygrep -H class {} ;
  pyfind -iname *.o -delete
  pyfind -iname *.py -xargs -exec pywc -l ;
  pyfind D:\\dev -iname node_modules -type d -cdup 1
  pyfind -iname *.dll -cdup 1 -abspath | pysetpath -o env.bat
  pyfind -iname *.mp3 -conc 4 -async -exec ffmpeg -i {} {dirname}\\{basename}.wav ;
  pyfind -mdate 2024-07-25
  pyfind -mdate 2024-07-25 2024-08-21
  pyfind -newer path/to/file
  pyfind D:\\dev -maxdepth 2 -gitdir -gitstat
  pyfind D:\\dev -maxdepth 2 -stat
  pyfind C:\\Qt\\6.7.1 -iname *.dll -bgrep "55 71 fe ff"
""")

async def async_main():

    args = expand_args()

    debug = False
    if len(args) > 0 and args[-1] == '-debug':
        args.pop(-1)
        debug = True
    
    if len(args) > 0 and args[-1] in ['-h', '--help']:
        print_help()
        return

    expr, paths, action, extraArgs = parse_args(args)

    if debug:
        print(expr); exit(0)

    tree, pred = expr_to_pred(expr)

    if len(paths) == 0:
        paths.append(".")
    
    walk_all(paths, pred, action, extraArgs)

    await action.wait()

def main():
    asyncio.run(async_main())

if __name__ == "__main__":
    main()