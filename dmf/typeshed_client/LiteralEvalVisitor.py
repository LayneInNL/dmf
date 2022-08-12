#  Copyright 2022 Layne Liu
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
import ast
from typing import Union, Tuple, Any

from dmf.typeshed_client.finder import SearchContext

_CMP_OP_TO_FUNCTION = {
    ast.Eq: lambda x, y: x == y,
    ast.NotEq: lambda x, y: x != y,
    ast.Lt: lambda x, y: x < y,
    ast.LtE: lambda x, y: x <= y,
    ast.Gt: lambda x, y: x > y,
    ast.GtE: lambda x, y: x >= y,
    ast.Is: lambda x, y: x is y,
    ast.IsNot: lambda x, y: x is not y,
    ast.In: lambda x, y: x in y,
    ast.NotIn: lambda x, y: x not in y,
}


class LiteralEvalVisitor(ast.NodeVisitor):
    def __init__(self, search_context: SearchContext) -> None:
        self.search_context = search_context

    def visit_Num(self, node: ast.Num) -> Union[int, float]:
        return node.n

    def visit_Str(self, node: ast.Str) -> str:
        return node.s

    def visit_Index(self, node: ast.Index) -> int:
        return self.visit(node.value)

    def visit_Tuple(self, node: ast.Tuple) -> Tuple[Any, ...]:
        return tuple(self.visit(elt) for elt in node.elts)

    def visit_Subscript(self, node: ast.Subscript) -> Any:
        value = self.visit(node.value)
        slc = self.visit(node.slice)
        return value[slc]

    def visit_Compare(self, node: ast.Compare) -> bool:
        if len(node.ops) != 1:
            raise NotImplementedError(
                f"Cannot evaluate chained comparison {ast.dump(node)}"
            )
        fn = _CMP_OP_TO_FUNCTION[type(node.ops[0])]
        return fn(self.visit(node.left), self.visit(node.comparators[0]))

    def visit_BoolOp(self, node: ast.BoolOp) -> bool:
        for val_node in node.values:
            val = self.visit(val_node)
            if (isinstance(node.op, ast.Or) and val) or (
                isinstance(node.op, ast.And) and not val
            ):
                return val
        return val

    def visit_Slice(self, node: ast.Slice) -> slice:
        lower = self.visit(node.lower) if node.lower is not None else None
        upper = self.visit(node.upper) if node.upper is not None else None
        step = self.visit(node.step) if node.step is not None else None
        return slice(lower, upper, step)

    def visit_Attribute(self, node: ast.Attribute) -> Any:
        val = node.value
        if not isinstance(val, ast.Name):
            raise NotImplementedError(f"Invalid code in stub: {ast.dump(node)}")
        if val.id != "sys":
            raise NotImplementedError(
                f"Attribute access must be on the sys module: {ast.dump(node)}"
            )
        if node.attr == "platform":
            return self.search_context.platform
        elif node.attr == "version_info":
            return self.search_context.version
        else:
            raise NotImplementedError(f"Invalid attribute on {ast.dump(node)}")
