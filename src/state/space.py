import ast
from typing import Tuple, List, Dict, Set


class Context:
    def __init__(self):
        self.content = None


class HContext:
    def __init__(self):
        self.content = None


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
    def __init__(self):
        self.content: Dict[Var, ContSensAddr] = None


class Obj:
    def __init__(self):
        self.content: Tuple[HContext, Dict[FieldName, ContSensAddr]] = None


class Store:
    def __init__(self):
        self.content: Dict[ContSensAddr, Set[Obj]] = None


class CallStack:
    def __init__(self):
        self.content: Tuple[Stmt, Context, ContSensAddr] = None
