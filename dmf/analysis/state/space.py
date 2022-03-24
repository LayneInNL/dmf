import logging
import typing

from .types import NumObjectAddress, StrObjectAddress, BytesObjectAddress, NoneObjectAddress, DefaultObject
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


Context = typing.NewType('Context', tuple)
HContext = typing.NewType('HContext', tuple)
Var = typing.NewType('Var', str)


# class Context:
#     def __init__(self):
#         self.context: List = []
#
#     def __repr__(self):
#         return self.context.__repr__()
#
#     def __str__(self):
#         return self.__repr__()
#
#
# class HContext:
#     def __init__(self):
#         self.h_context: List = []


class Var:
    def __init__(self, var):
        self.var: str = var


class FieldName:
    def __init__(self, filed_name):
        self.field_name: str = filed_name


# class ContSensAddr:
#     pass
#
#
# class VarContSensAddr(ContSensAddr):
#     def __init__(self):
#         self.address: Tuple[Var, Context] = None
#
#
# class FiledNameContSensAddr(ContSensAddr):
#     def __init__(self):
#         self.address: Tuple[FieldName, HContext] = None
#

class StmtID:
    def __init__(self, CFG):
        self.start_id = CFG.start.bid
        self.curr_id = self.start_id
        logging.debug('Curr id is {}'.format(self.curr_id))
        self.blocks = CFG.blocks
        self.flows = CFG.flows

    def curr_stmt(self):
        curr_block = self.blocks[self.curr_id]
        return curr_block.stmt[0]

    def goto_next_stmt_id(self, bid):
        id_list = self.flows[bid]
        next_id = None
        for val in id_list:
            next_id = val
        self.curr_id = next_id


class DataStack:
    def __init__(self):
        # data_stack contains Dict[Var, ContSensAddr]
        self.data_stack: Stack = Stack()
        self.create_push_frame()

    def st(self, var: Var, context: Context):
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

    def create_push_frame(self, default_init=True):
        frame = {}
        if default_init:
            frame[NumObjectAddress.name] = NumObjectAddress.address
            frame[StrObjectAddress.name] = StrObjectAddress.address
            frame[BytesObjectAddress.name] = BytesObjectAddress.address
            frame[NoneObjectAddress.name] = NoneObjectAddress.address
        self.push_frame(frame)
        return self.top_frame()

    def __repr__(self):
        result = ''
        for key, value in self.top_frame().items():
            line = '{}, {}\n'.format(key, value)
            result += line

        return result


# class Obj:
#     def __init__(self, h_context, field_map):
#         self.obj: Tuple[HContext, Dict[FieldName, ContSensAddr]] = (h_context, field_map)


class Store:
    def __init__(self, default_initialize=True):
        self.store = defaultdict(set)
        if default_initialize:
            self._initialize()

    def _initialize(self):
        for address in [NumObjectAddress.address, StrObjectAddress.address,
                        BytesObjectAddress.address, NoneObjectAddress.address]:
            self.store[address].add(DefaultObject.obj)

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
