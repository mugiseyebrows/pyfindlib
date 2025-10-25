from pyfindlib.tok import T, TOK, TOK_AS_INT, TOK_AS_STR, tok_pred, tok_pred_nargs, tok_pred_noargs
from pyfindlib.shared import parse_size, NO_STAT, STAT1, STAT2
from pyfindlib.types import ExtraArgs
from pyfindlib import predicate
import dateutil.parser
import re
import sys
from pyfindlib.types import parse_address_range, parse_int, parse_float, parse_float_range, FloatRange
from pyfindlib.action import ActionBase, ActionPrint, ActionExec, ActionDelete, ActionTouch, ActionGitStatus, ActionCopyOrMove, ActionExtStat, ActionHash, ActionDu

def parse_xlgrep_arg(s):
    if isinstance(s, list):
        if len(s) == 2 and isinstance(s[0], (int, float)) and isinstance(s[1], (int, float)):
            val = FloatRange(*s)
            return val
        else:
            return s # list of values
    ar = parse_address_range(s)
    if ar:
        return ar
    i = parse_int(s)
    if i is not None:
        return i
    f = parse_float(s)
    if f is not None:
        return f
    fr = parse_float_range(s)
    if fr:
        return fr
    return s

def get_pred_fn(pred_type):
    return {
        TOK.type: predicate.type,
        TOK.mmin: predicate.mmin,
        TOK.iname: predicate.iname,
        TOK.name: predicate.name,
        TOK.newer: predicate.newer,
        TOK.newermt: predicate.newermt,
        TOK.newerct: predicate.newerct,
        TOK.ctime: predicate.ctime,
        TOK.mtime: predicate.mtime,
        TOK.size: predicate.size,
        TOK.grep: predicate.grep,
        TOK.igrep: predicate.igrep,
        TOK.bgrep: predicate.bgrep,
        TOK.path: predicate.path,
        TOK.ipath: predicate.ipath,
        TOK.mdate: predicate.mdate,
        TOK.cpptmp: predicate.cpptmp,
        TOK.docgrep: predicate.docgrep,
        TOK.xlgrep: predicate.xlgrep,
        TOK.zippath: predicate.zippath,
        TOK.zipipath: predicate.zipipath,
        TOK.image: predicate.image,
        TOK.video: predicate.video,
        TOK.book: predicate.book,
        TOK.dirwith: predicate.dirwith,
        TOK.dirwithf: predicate.dirwithf,
        TOK.dirwithd: predicate.dirwithd,
    }[pred_type]

def hex_parse(s):
    res = []
    for i in range(0, len(s), 2):
        res.append(int(s[i:i+2], 16))
    return bytes(res)

def parse_bgrep_arg(arg: str):
    return hex_parse(re.sub('\\s+','', arg))

class Node:
    def __init__(self, children = None, pred = None, args = None, op = None):
        self.children = children
        self.pred = pred
        self.args = args
        self.op = op

class NodeOpt(Node):
    def __init__(self, tokens: list[T]):
        pred, args = tokens[0], tokens[1:]
        super().__init__(None, pred, args)

    def opttype(self):
        return TOK_AS_INT[self.pred.cont]

    def intval(self):
        return int(self.args[0].cont)
    
    def strval(self, default = None):
        if len(self.args) > 0:
            return self.args[0].cont
        return default
    
    def strvals(self):
        return [a.cont for a in self.args]

    def __repr__(self):
        return self.pred + ' ' + ' '.join(self.args)

class NodeOr(Node):
    pass

class NodeAnd(Node):
    pass

class NodePred(Node):
    pass

class NodeAnyPred(NodePred):
    
    def __call__(self, name, path, isdir):
        return True
    def __repr__(self):
        return '-anything'

def parse_fn_args(pred_type, args: list[T]):

    if pred_type in tok_pred_nargs:
        args_ = [arg.cont for arg in args]
    elif pred_type in tok_pred_noargs:
        args_ = None
    else:
        args_ = args[0].cont

    res = None
    if pred_type == TOK.size:
        res = parse_size(args_)
    elif pred_type == TOK.type:
        res = args_
        if res not in ['d','f']:
            raise ValueError("{} is not a valid type".format(args_))
    elif pred_type in [TOK.newermt, TOK.newerct]:
        res = dateutil.parser.parse(args_)
    elif pred_type in [TOK.mtime, TOK.ctime, TOK.mmin]:
        res = float(args_)
    elif pred_type == TOK.mdate:
        res = [dateutil.parser.parse(a).date() for a in args_]
    elif pred_type == TOK.newer:
        res = predicate._getmtime(args_)
    elif pred_type == TOK.xlgrep:
        res = [parse_xlgrep_arg(a) for a in args_]
    elif pred_type == TOK.bgrep:
        res = parse_bgrep_arg(args_)
    else:
        res = args_

    return res

class NodeSimplePred(NodePred):
    def __init__(self, tokens):
        pred, args = tokens[0], tokens[1:]
        pred_type = TOK_AS_INT[pred.cont]
        super().__init__(None, pred, args)
        pred_fn = get_pred_fn(pred_type)
        
        self.pred_type = pred_type
        self.pred_fn = pred_fn
        self.args_ = parse_fn_args(pred_type, args)

    def __call__(self, name, path, isdir):
        return self.pred_fn(name, path, isdir, self.args_)

    def __repr__(self):
        return self.pred + ' ' + ' '.join(self.args)

class NodeComplexPred(NodePred):
    def __init__(self, op, children):
        super().__init__(children, None, None, op)

    def __repr__(self):
        if len(self.children) == 1:
            return f'{TOK_AS_STR[self.op]} {self.children[0]}'
        elif len(self.children) == 2:
            return f'({self.children[0]} {TOK_AS_STR[self.op]} {self.children[1]})'
        else:
            return f'error: len(self.children) = {len(self.children)}'

    def __call__(self, name, path, isdir):
        res = self.children[0](name, path, isdir)
        if res is None:
            return
        if self.op == TOK.not_:
            return not res
        elif self.op == TOK.or_:
            if res:
                return True
            return self.children[1](name, path, isdir)
        elif self.op == TOK.and_:
            if not res:
                return False
            return self.children[1](name, path, isdir)

def parse_exec(tokens: list[T]):
    res: list[T] = []
    while len(tokens) > 0 and tokens[0].type != TOK.semicolon:
        res.append(tokens.pop(0))
    if len(tokens) > 0 and tokens[0].type == TOK.semicolon:
        tokens.pop(0)
    else:
        raise ValueError("exec action should be terminated with ;")
    return NodeOpt(res)

def parse_pred(tokens: list[T], opts):
    res: list[T] = []
    first = tokens[0].type
    if first == TOK.op_par:
        return parse_par(tokens, opts)
    if first == TOK.exec:
        return parse_exec(tokens)
    res.append(tokens.pop(0))
    while len(tokens) > 0 and tokens[0].type == TOK.val:
        res.append(tokens.pop(0))
    if res[0].cont in ['-print', '-delete', '-move', '-copy', '-rename', '-touch', '-stat', '-stat2', '-extstat', '-gitstat',
                       '-basename', '-abspath', '-cdup', '-maxdepth', '-cdin', '-conc', '-flush', '-flat', '-tree', '-noover',
                       '-async', '-first', '-trail', '-skip', '-xargs', '-pstdout', '-pstderr', '-output', '-hash', '-relpath', 
                       '-du', '-h']:
        #print("parse_pred opt", res)
        return NodeOpt(res)
    #print("parse_pred pred", res)
    return NodeSimplePred(res)
    
def parse_not(tokens: list[T], opts):
    tokens.pop(0)
    return NodeComplexPred(TOK.not_, [parse_pred(tokens, opts)])

def find_close_par(tokens: list[T]):
    i = len(tokens) - 1
    while i > 0 and tokens[i].type != TOK.cl_par:
        i -= 1
    if tokens[i].type != TOK.cl_par:
        raise ValueError('parenthesis error')
    return i

def find_and(nodes: list[Node]):
    for i, node in enumerate(nodes):
        if isinstance(node, NodeAnd):
            return i

def find_or(nodes: list[Node]):
    for i, node in enumerate(nodes):
        if isinstance(node, NodeOr):
            return i

def parse_par(tokens: list[T], opts):
    res = []
    ix = find_close_par(tokens)
    for i in range(ix + 1):
        res.append(tokens.pop(0))
    return parse_tree(res[1:-1], opts)

def parse_or(tokens: list[T]):
    tokens.pop(0)
    return NodeOr()

def parse_and(tokens: list[T]):
    tokens.pop(0)
    return NodeAnd()

def insert_ands(nodes: list[Node]):
    if len(nodes) == 0:
        return []
    # insert explicit and
    res = [nodes.pop(0)]
    while len(nodes) > 0:
        node = nodes.pop(0)
        if isinstance(res[-1], NodePred) and isinstance(node, NodePred):
            res.append(NodeAnd())
        res.append(node)
    return res

def filter_opts(nodes: list[Node], opts: list[NodeOpt]):
    notopts = []
    for node in nodes:
        if isinstance(node, NodeOpt):
            opts.append(node)
        else:
            notopts.append(node)
    return notopts

def validate_parenthesis(tokens):
    op_par_count = 0
    cl_par_count = 0
    for token in tokens:
        if token.type == TOK.op_par:
            op_par_count += 1
        elif token.type == TOK.cl_par:
            cl_par_count += 1
    if op_par_count != cl_par_count:
        raise ValueError(f'unbalanced parenthesis, {op_par_count} opening {cl_par_count} closing')

def parse_tree(tokens: list[T], opts: list[Node]):
    nodes = []
    validate_parenthesis(tokens)
    tokens = list(tokens)
    while len(tokens) > 0:
        if tokens[0].type == TOK.key or tokens[0].type in [TOK.op_par, TOK.exec]:
            nodes.append(parse_pred(tokens, opts))
        elif tokens[0].type == TOK.not_:
            nodes.append(parse_not(tokens, opts))
        elif tokens[0].type == TOK.or_:
            nodes.append(parse_or(tokens))
        elif tokens[0].type == TOK.and_:
            nodes.append(parse_and(tokens))
        else:
            raise ValueError(f'parse_tree error, unexpected token {tokens[0]}')

    nodes = filter_opts(nodes, opts)

    nodes = insert_ands(nodes)
    # build a tree
    
    while True:
        ix = find_and(nodes)
        if ix is None:
            break
        ix -= 1
        node1, op, node2 = nodes[ix:ix+3]
        node = NodeComplexPred(TOK.and_, [node1, node2])
        nodes = nodes[:ix] + [node] + nodes[ix+3:]

    while True:
        ix = find_or(nodes)
        if ix is None:
            break
        ix -= 1
        node1, op, node2 = nodes[ix:ix+3]
        node = NodeComplexPred(TOK.or_, [node1, node2])
        nodes = nodes[:ix] + [node] + nodes[ix+3:]
    
    if len(nodes) == 0:
        nodes.append(NodeAnyPred())

    if len(nodes) != 1:
        raise ValueError(f'parse error len(nodes) = {len(nodes)}')

    return nodes[0]

def is_number(val):
    try:
        float(val)
        return True
    except ValueError:
        return False

def is_size(val):
    res = parse_size(val)
    return res is not None

def filter_paths(tokens: list[T]):
    paths = []
    while len(tokens) > 0 and not tokens[0].cont.startswith('-') and tokens[0].cont not in ['(', ')']:
        token = tokens.pop(0)
        paths.append(token.cont)
    return paths

def has_opt(opts: list[NodeOpt], opttype) -> bool:
    for opt in opts:
        if opt.opttype() == opttype:
            return True
    return False

def get_opt(opts: list[NodeOpt], opttype) -> NodeOpt:
    for opt in opts:
        if opt.opttype() == opttype:
            return opt

def get_opts(opts: list[NodeOpt], opttype) -> list[NodeOpt]:
    res = []
    for opt in opts:
        if opt.opttype() == opttype:
            res.append(opt)
    return res

def get_extra_args(opts: list[NodeOpt]):
    maxdepth_opt = get_opt(opts, TOK.maxdepth)
    maxdepth = maxdepth_opt.intval() if maxdepth_opt else 0
    first_opt = get_opt(opts, TOK.first)
    first = first_opt.intval() if first_opt else None
    skip = []
    for opt in get_opts(opts, TOK.skip):
        skip.extend(opt.strvals())
    return ExtraArgs(maxdepth, first, skip)

def get_action(opts: list[NodeOpt]):
    exec_opt = get_opt(opts, TOK.exec)
    
    async_ = has_opt(opts, TOK.async_)
    conc_opt = get_opt(opts, TOK.conc)
    conc = conc_opt.intval() if conc_opt else None

    xargs = has_opt(opts, TOK.xargs)
    
    delete_opt = get_opt(opts, TOK.delete)
    gitstat_opt = get_opt(opts, TOK.gitstat)

    abspath = has_opt(opts, TOK.abspath)
    relpath = has_opt(opts, TOK.relpath)
    basename = has_opt(opts, TOK.basename)

    output_opt = get_opt(opts, TOK.output)

    flat = has_opt(opts, TOK.flat)
    tree = has_opt(opts, TOK.tree)

    rename = has_opt(opts, TOK.rename)

    noover = has_opt(opts, TOK.noover)

    stat = has_opt(opts, TOK.stat)
    stat2 = has_opt(opts, TOK.stat2)

    copy_opt = get_opt(opts, TOK.copy)
    move_opt = get_opt(opts, TOK.move)

    extstat_opt = get_opt(opts, TOK.extstat)
    gitstat_opt = get_opt(opts, TOK.gitstat)
    hash_opt = get_opt(opts, TOK.hash)
    touch_opt = get_opt(opts, TOK.touch)
    du_opt = get_opt(opts, TOK.du)

    trail = has_opt(opts, TOK.trail)
    flush = has_opt(opts, TOK.flush)
    cdin = has_opt(opts, TOK.cdin)
    pstdout = has_opt(opts, TOK.pstdout)
    pstderr = has_opt(opts, TOK.pstderr)
    human_readable = has_opt(opts, TOK.h)

    if exec_opt:
        action = ActionExec(exec_opt.args, async_, conc, xargs, cdin, pstdout, pstderr)
    elif copy_opt:
        copy_dst = copy_opt.strval()
        action = ActionCopyOrMove(True, copy_dst, flat, tree, rename, noover)
    elif move_opt:
        move_dst = move_opt.strval()
        action = ActionCopyOrMove(False, move_dst, flat, tree, rename, noover)
    elif extstat_opt:
        action = ActionExtStat()
    elif delete_opt:
        action = ActionDelete()
    elif gitstat_opt:
        action = ActionGitStatus()
    elif touch_opt:
        action = ActionTouch()
    elif hash_opt:
        action = ActionHash(hash_opt.strval('md5'), abspath, relpath, basename)
    elif du_opt:
        action = ActionDu(human_readable, flush, abspath, relpath, basename)
    else:
        output = None
        if output_opt:
            output = output_opt.strval()
        if stat:
            stat_ = STAT1
        elif stat2:
            stat_ = STAT2
        else:
            stat_ = NO_STAT
        action = ActionPrint(stat_, trail, flush, basename, output)

    cdup_opt = get_opt(opts, TOK.cdup)
    cdup = cdup_opt.intval() if cdup_opt else 0

    action.setOptions(cdup, abspath)

    return action

def parse(args = None) -> tuple[list[str], NodePred, ActionBase, ExtraArgs]:

    if args is None:
        args = sys.argv[1:]

    def m(arg):
        if arg in ['(',')','-or','-and','-not','-exec',';','\\;']:
            return T(TOK_AS_INT.get(arg), arg)
        elif arg.startswith('-'):
            if is_number(arg):
                return T(TOK.val, arg)
            elif is_size(arg):
                return T(TOK.val, arg)
            else:
                return T(TOK.key, arg)
        else:
            return T(TOK.val, arg)
        
    tokens = [m(arg) for arg in args]

    paths = filter_paths(tokens)

    opts = []

    pred = parse_tree(tokens, opts)

    action = get_action(opts)

    extraArgs = get_extra_args(opts)

    return paths, pred, action, extraArgs

def parse_test():
    args_ = '-iname *.py -mmin -10'
    args = args_.split(' ')
    paths, pred, action, extraArgs = parse(args)
    
if __name__ == "__main__":
    parse_test()