import logging

from .state.space import StmtID, DataStack, Store, CallStack, Context
from .state.types import NumObjectAddress, BoolObjectAddress, StrObjectAddress, NoneObjectAddress

import ast


class PointsToAnalysis:
    def __init__(self, CFG):
        # Control flow graph, it contains program points and ast nodes.
        self.stmt_id = StmtID(CFG)
        self.data_stack = DataStack()
        self.store = Store()
        self.call_stack = CallStack()
        self.context: Context = Context(())

    def iteration(self):
        while self.stmt_id.curr_id is not None:
            self.transition()

    def transition(self):
        stmt = self.stmt_id.curr_stmt()
        self.stmt_id.goto_next_stmt_id(self.stmt_id.curr_id)
        self.transfer(stmt)

    def transfer(self, stmt: ast.AST):
        type_of_stmt = type(stmt)
        if type_of_stmt == ast.Assign:
            self.do_assign(stmt)
        elif type_of_stmt == ast.Pass:
            pass

    def do_assign(self, stmt: ast.Assign):
        type_of_value = type(stmt.value)
        if type_of_value == ast.Num:
            right_addr = self.data_stack.st(NumObjectAddress.name, self.context)
        elif type_of_value == ast.NameConstant:
            if stmt.value.value in [True, False]:
                right_addr = self.data_stack.st(BoolObjectAddress.name, self.context)
            else:
                right_addr = self.data_stack.st(NoneObjectAddress.name, self.context)
        elif type_of_value == ast.Name:
            right_addr = self.data_stack.st(stmt.value.id, self.context)
        right_obj = self.store.get(right_addr)
        left_address = self.data_stack.st(stmt.targets[0].id, self.context)
        self.store.insert(left_address, right_obj)
