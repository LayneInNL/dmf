from .state.space import DataStack, Store, CallStack, Context
from .state.types import BoolFalseObjectAddress, BoolTrueObjectAddress, NoneObjectAddress

from typing import List, Tuple, Any

import ast


class PointsToAnalysis:
    def __init__(self, blocks):
        self.blocks = blocks
        # Control flow graph, it contains program points and ast nodes.
        self.data_stack: DataStack = DataStack()
        self.store: Store = Store()
        self.call_stack: CallStack = CallStack()
        self.context: Context = Context(())

    def transfer(self, label: int) -> List[Tuple[str, Any]]:
        # We would like to refactor the code with the strategy in ast.NodeVisitor
        stmt = self.blocks[label].stmt[0]
        method = 'handle_' + stmt.__class__.__name__
        handler = getattr(self, method)
        return handler(stmt)

    def handle_Assign(self, stmt: ast.Assign) -> List[Tuple[str, Any]]:
        type_of_value = type(stmt.value)
        right_address = None
        # if type_of_value == ast.Num:
        #     right_address = self.data_stack.st(NumObjectAddress.name, self.context)
        # elif type_of_value == ast.NameConstant:
        #     if stmt.value.value in [True, False]:
        #         right_address = self.data_stack.st(BoolObjectAddress.name, self.context)
        #     else:
        #         right_address = self.data_stack.st(NoneObjectAddress.name, self.context)
        # elif type_of_value in [ast.Str, ast.FormattedValue, ast.JoinedStr]:
        #     if type_of_value == ast.FormattedValue:
        #         logging.warning('FormattedValue is encountered. Please double check...')
        #     right_address = self.data_stack.st(StrObjectAddress.name, self.context)
        # elif type_of_value == ast.Bytes:
        #     right_address = self.data_stack.st(BytesObjectAddress.name, self.context)
        # elif type_of_value == ast.Name:
        #     right_address = self.data_stack.st(stmt.value.id, self.context)
        if type_of_value == ast.NameConstant:
            right_address = self.handle_NameConstant(stmt.value)
        elif type_of_value == ast.Name:
            right_address = self.data_stack.st(stmt.value.id, self.context)
        assert right_address is not None
        right_objs = self.store.get(right_address)
        left_name = stmt.targets[0].id
        left_address = self.data_stack.st(left_name, self.context)
        self.store.insert_many(left_address, right_objs)
        return [(left_name, self.store.get(left_address))]

    def handle_NameConstant(self, expr):
        if expr.value:
            right_address = self.data_stack.st(BoolTrueObjectAddress.name, None)
        elif not expr.value:
            right_address = self.data_stack.st(BoolFalseObjectAddress.name, None)
        else:
            right_address = self.data_stack.st(NoneObjectAddress.name, None)

        return right_address

    def handle_Pass(self, stmt: ast.Pass):
        return []
