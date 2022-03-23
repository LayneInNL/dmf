import logging

from .types import Num
from collections import defaultdict
from typing import Tuple, List, Dict, Set


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
        self.context: List = []

    def __repr__(self):
        return self.context.__repr__()

    def __str__(self):
        return self.__repr__()


class HContext:
    def __init__(self):
        self.h_context: List = []


class Var:
    def __init__(self, var):
        self.var: str = var


class FieldName:
    def __init__(self, filed_name):
        self.field_name: str = filed_name


class ContSensAddr:
    pass


class VarContSensAddr(ContSensAddr):
    def __init__(self):
        self.address: Tuple[Var, Context] = None


class FiledNameContSensAddr(ContSensAddr):
    def __init__(self):
        self.address: Tuple[FieldName, HContext] = None


class StmtID:
    def __init__(self, CFG):
        self.curr_id: int = CFG.start.bid
        logging.debug('Curr id is {}'.format(self.curr_id))
        self.blocks = CFG.blocks
        self.flows = CFG.flows

    def curr_stmt(self):
        curr_block = self.blocks[self.curr_id]
        return curr_block.stmt[0]

    def goto_next_stmt_id(self, bid):
        id_list = self.flows[bid]
        if not id_list:
            return None
        for val in id_list:
            next_id = val
        return next_id


class DataStack:
    def __init__(self):
        # data_stack contains Dict[Var, ContSensAddr]
        self.data_stack: Stack = Stack()
        initial_frame = self.create_frame()
        self.push_frame(initial_frame)

    def st(self, var, context):
        logging.debug('Test st: %s %s', var, context)
        top_frame = self.top_frame()
        if var not in top_frame:
            top_frame[var] = (var, context)
        return top_frame[var]

    def top_frame(self):
        return self.data_stack.top()

    def push_var(self, var, address):
        top_frame = self.top_frame()
        top_frame[var] = address

    def push_frame(self, frame):
        self.data_stack.push(frame)

    def create_frame(self, default_init=True):
        frame = {}
        if default_init:
            frame[Num.name] = Num.address
        return frame

    def __repr__(self):
        result = ''
        for key, value in self.top_frame().items():
            line = '{}, {}\n'.format(key, value)
            result += line

        return result


class Obj:
    def __init__(self, h_context, field_map):
        self.obj: Tuple[HContext, Dict[FieldName, ContSensAddr]] = (h_context, field_map)


class Store:
    def __init__(self):
        self.store: Dict[ContSensAddr, Set[Obj]] = defaultdict(set)
        obj = (0, None)
        self.store[Num.address].add(obj)

    def insert(self, address, obj):
        self.store[address] = obj

    def get(self, address):
        return self.store[address]

    def __repr__(self):
        result = ''
        for key, value in self.store.items():
            line = '{}, {}\n'.format(key, value)
            result += line

        return result


class CallStack:
    def __init__(self):
        # call_stack contains Tuple[StmtID, Context, ContSensAddr]
        self.call_stack: Stack = Stack()


class AbstractState:
    def __init__(self, CFG):
        self.stmt_id = StmtID(CFG)
        self.data_stack = DataStack()
        self.store = Store()
        self.call_stack = CallStack()
        self.context = Context()
