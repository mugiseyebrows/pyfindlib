# pyfindlib

Shell utility resembling findutils, small, extendable and windows-friendly

# Install

```shell
pip install pyfindlib
```

# Use

```
usage: pyfind [PATHS] [OPTIONS] [CONDITIONS] [-async] [-exec cmd args {} ;] [-delete] [-print]

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
  pyfind D:\dev -iname node_modules -type d -cdup 1
  pyfind -iname *.dll -cdup 1 -abspath | pysetpath -o env.bat
  pyfind -iname *.mp3 -conc 4 -async -exec ffmpeg -i {} {dirname}\{basename}.wav ;
  pyfind -mdate 2024-07-25
  pyfind -mdate 2024-07-25 2024-08-21
  pyfind -newer path/to/file
  pyfind D:\dev -maxdepth 2 -gitdir -gitstat
  pyfind D:\dev -maxdepth 2 -stat
  pyfind C:\Qt\6.7.1 -iname *.dll -bgrep "55 71 fe ff"

```

# See also

[https://github.com/mugiseyebrows/mugi-cli](https://github.com/mugiseyebrows/mugi-cli)