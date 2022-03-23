import logging

from .state.space import AbstractState, StmtID, DataStack, Store, CallStack, Context
from .state.types import Num, String

import ast


class PointsToAnalysis:
    def __init__(self, CFG):
        # Control flow graph, it contains program points and ast nodes.
        self.stmt_id = StmtID(CFG)
        self.data_stack = DataStack()
        self.store = Store()
        self.call_stack = CallStack()
        self.context = Context()

    def iteration(self):
        while self.stmt_id.curr_id is not None:
            self.transition()

    def transition(self):
        stmt = self.stmt_id.curr_stmt()
        next_stmt_id = self.stmt_id.next_stmt_id(self.stmt_id.curr_id)
        if type(stmt) == ast.Assign:
            left_var_name = stmt.targets[0].id
            if type(stmt.value) == ast.Num:
                left_var_address = self.data_stack.st(left_var_name, self.context)
                right_var_address = self.data_stack.st(Num.name, self.context)
                right_var_object = self.store.get(right_var_address)
                self.store.insert(left_var_address, right_var_object)
            elif type(stmt.value) == ast.Name:
                right_var_name = stmt.value.id
                left_var_address = self.data_stack.st(left_var_name, self.context)
                right_var_address = self.data_stack.st(right_var_name, self.context)
                right_var_object = self.store.get(right_var_address)
                self.store.insert(left_var_address, right_var_object)
        elif type(stmt) == ast.Pass:
            pass
        self.stmt_id.curr_id = next_stmt_id
