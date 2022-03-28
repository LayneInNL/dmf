import logging
import typing
from typing import Dict, Tuple, Set
from collections import defaultdict

from .types import BUILTIN_CLASSES

Context = typing.NewType('Context', tuple)
HContext = typing.NewType('HContext', tuple)
Var = typing.NewType('Var', str)


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
        self.data_stack = []
        initial_frame = self.new_frame()
        self.push_frame(initial_frame)

    def st(self, var: Var, context: Context):
        logging.debug('Test st: %s %s', var, context)
        top_frame = self.top()
        if var not in top_frame:
            logging.info('{} is not in data stack, make one'.format(var))
            top_frame[var] = (var, context)
        return top_frame[var]

    def top(self):
        return self.data_stack[-1]

    def push_var(self, var, address):
        top_frame = self.top()
        top_frame[var] = address

    def push_frame(self, frame):
        self.data_stack.append(frame)

    def new_frame(self, default_init=True):
        frame = {}
        if default_init:
            for cls in BUILTIN_CLASSES:
                frame[cls.name] = cls.address
        return frame

    def __repr__(self):
        result = ''
        for key, value in self.top().items():
            line = '{}, {}\n'.format(key, value)
            result += line

        return result


class Store:
    def __init__(self, default_initialize=True):
        self.store: Dict[Tuple, Set] = defaultdict(set)
        if default_initialize:
            self._initialize()

    def _initialize(self):
        for cls in BUILTIN_CLASSES:
            self.insert_one(cls.address, cls.obj)
            print(cls.obj)

    def insert_one(self, address, obj):
        self.store[address].add(obj)

    def insert_many(self, address, objs):
        self.store[address].update(objs)

    def get(self, address) -> Set:
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
        self.call_stack = []
