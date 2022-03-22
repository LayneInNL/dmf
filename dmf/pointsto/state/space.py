import ast
from typing import Tuple, Dict, Set


class Stack:
    def __init__(self):
        self.stack = []

    def push(self, elt):
        self.stack.append(elt)

    def pop(self):
        self.stack.pop()

    def top(self):
        return self.stack[-1]

    def len(self):
        return len(self.stack)


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


class StmtID:
    def __init__(self):
        self.stmt_id: int = None


class DataStack:
    def __init__(self):
        # data_stack contains Dict[Var, ContSensAddr]
        self.data_stack: Stack = Stack()

    def st(self, var):
        top_frame = self.data_stack.top()
        if var in top_frame:
            return top_frame[var]


class Obj:
    def __init__(self):
        self.obj: Tuple[HContext, Dict[FieldName, ContSensAddr]] = None


class Store:
    def __init__(self):
        self.store: Dict[ContSensAddr, Set[Obj]] = {}


class CallStack:
    def __init__(self):
        # call_stack contains Tuple[StmtID, Context, ContSensAddr]
        self.call_stack: Stack = Stack()


class AbstractState:
    def __init__(self):
        self.stmt_id = StmtID()
        self.data_stack = DataStack()
        self.store = Store()
        self.call_stack = CallStack()
        self.context = Context()
