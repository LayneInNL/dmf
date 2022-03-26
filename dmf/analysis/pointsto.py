import logging

from .state.space import StmtID, DataStack, Store, CallStack, Context
from .state.types import NumObjectAddress, BoolObjectAddress, StrObjectAddress, BytesObjectAddress, NoneObjectAddress

import ast


class PointsToAnalysis:
    def __init__(self, blocks):
        self.blocks = blocks
        # Control flow graph, it contains program points and ast nodes.
        self.data_stack = DataStack()
        self.store = Store()
        self.call_stack = CallStack()
        self.context: Context = Context(())

    def transfer(self, label: int):
        # We would like to refactor the code with the strategy in ast.NodeVisitor
        stmt = self.blocks[label].stmt
        method = 'handle_' + stmt.__class__.__name__
        handler = getattr(self, method)
        return handler()

    def handle_Assign(self, stmt: ast.Assign):
        type_of_value = type(stmt.value)
        right_address = None
        if type_of_value == ast.Num:
            right_address = self.data_stack.st(NumObjectAddress.name, self.context)
        elif type_of_value == ast.NameConstant:
            if stmt.value.value in [True, False]:
                right_address = self.data_stack.st(BoolObjectAddress.name, self.context)
            else:
                right_address = self.data_stack.st(NoneObjectAddress.name, self.context)
        elif type_of_value in [ast.Str, ast.FormattedValue, ast.JoinedStr]:
            if type_of_value == ast.FormattedValue:
                logging.warning('FormattedValue is encountered. Please double check...')
            right_address = self.data_stack.st(StrObjectAddress.name, self.context)
        elif type_of_value == ast.Bytes:
            right_address = self.data_stack.st(BytesObjectAddress.name, self.context)
        elif type_of_value == ast.Name:
            right_address = self.data_stack.st(stmt.value.id, self.context)
        assert right_address is not None
        right_objs = self.store.get(right_address)
        left_name = stmt.targets[0].id
        left_address = self.data_stack.st(left_name, self.context)
        self.store.insert_into(left_address, right_objs)
        return [(left_name, self.store.get(left_address))]

    def handle_Pass(self, stmt: ast.Pass):
        return []
