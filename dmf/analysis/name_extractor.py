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
from typing import Any


class NameExtractor(ast.NodeVisitor):
    def __init__(self):
        self.names = set()

    def build(self, ast):
        self.visit(ast)
        return self.names

    def visit_Assign(self, node: ast.Assign):
        assert len(node.targets) == 1
        self.visit(node.targets[0])

    def visit_Name(self, node: ast.Name) -> Any:
        self.names.add(node.id)

    def visit_Attribute(self, node: ast.Attribute) -> Any:
        self.visit(node.value)

    def visit_Subscript(self, node: ast.Subscript) -> Any:
        self.visit(node.value)

    def visit_List(self, node: ast.List) -> Any:
        for elt in node.elts:
            self.visit(elt)

    def visit_Tuple(self, node: ast.Tuple) -> Any:
        for elt in node.elts:
            self.visit(elt)
