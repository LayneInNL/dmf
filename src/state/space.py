import ast
from typing import Tuple, Dict, Set


class Context:
    def __init__(self):
        self.content: Tuple = None


class HContext:
    def __init__(self):
        self.content: Tuple = None


class Var:
    def __init__(self):
        self.content: str = None


class FieldName:
    def __init__(self):
        self.content: str = None


class ContSensAddr:
    pass


class VarContSensAddr(ContSensAddr):
    def __init__(self):
        self.content: Tuple[Var, Context] = None


class FiledNameContSensAddr(ContSensAddr):
    def __init__(self):
        self.content: Tuple[FieldName, HContext] = None


class Stmt:
    def __init__(self):
        self.content: ast.AST = None


class Stack:
    def __init__(self, content=None):
        self.content: Dict[Var, ContSensAddr] = {} if content is None else content


class Obj:
    def __init__(self):
        self.content: Tuple[HContext, Dict[FieldName, ContSensAddr]] = None


class Store:
    def __init__(self, content=None):
        self.content: Dict[ContSensAddr, Set[Obj]] = {} if content is None else content


class CallStack:
    def __init__(self):
        self.content: Tuple[Stmt, Context, ContSensAddr] = None


class AbstractState:
    def __init__(self):
        self.stmt = Stmt()
        self.stack = Stack()
        self.store = Store()
        self.call_stack = CallStack()
        self.context = Context()
