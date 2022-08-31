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

from __future__ import annotations

import ast
import os
from collections import defaultdict
from typing import Dict, List, Tuple, Set, Optional, Any

import astor
import graphviz as gv


class TempVariableName:
    counter = 0

    @classmethod
    def generate(cls) -> str:
        cls.counter += 1
        return f"_var{cls.counter}"


class BlockId:
    counter: int = 0

    @classmethod
    def gen_block_id(cls) -> int:
        cls.counter += 1
        return cls.counter


class BasicBlock:
    def __init__(self, bid: int):
        self.bid: int = bid
        self.stmt = []
        self.prev: List[int] = []
        self.next: List[int] = []

    def is_empty(self) -> bool:
        return len(self.stmt) == 0

    def has_next(self) -> bool:
        return len(self.next) != 0

    def has_previous(self) -> bool:
        return len(self.prev) != 0

    def remove_from_prev(self, prev_bid: int) -> None:
        if prev_bid in self.prev:
            self.prev.remove(prev_bid)

    def remove_from_next(self, next_bid: int) -> None:
        if next_bid in self.next:
            self.next.remove(next_bid)

    def stmt_to_code(self) -> str:
        code = str(self.bid) + "\n"
        for stmt in self.stmt:
            line = astor.to_source(stmt)
            code += (
                line.split("\n")[0] + "\n"
                if isinstance(
                    stmt,
                    (
                        ast.If,
                        ast.For,
                        ast.Try,
                        ast.While,
                        ast.With,
                        ast.FunctionDef,
                        ast.ClassDef,
                        ast.excepthandler,
                    ),
                )
                else line
            )
        return code

    def __str__(self):
        return "Block ID: {}".format(self.bid)


def add_stmt(block: BasicBlock, stmt) -> None:
    assert not block.stmt
    block.stmt.append(stmt)


class CFG:
    def __init__(self, name: str):
        self.name: str = name
        self.start_block: Optional[BasicBlock] = None
        self.final_block: Optional[BasicBlock] = None
        self.sub_cfgs: Dict[int, CFG] = {}
        self.blocks: Dict[int, BasicBlock] = {}
        self.edges: Dict[Tuple[int, int], Optional[ast.AST]] = {}
        self.graph: Optional[gv.dot.Digraph] = None

        self.flows: Set[Tuple[int, int]] = set()

        self.call_return_inter_flows: Set[
            Tuple[int, int, int, int, int, int, int, int, int]
        ] = set()
        self.classdef_inter_flows: Set[Tuple[int, int]] = set()
        self.setter_inter_flows: Set[Tuple[int, int, int]] = set()
        self.getter_inter_flows: Set[Tuple[int, int, int]] = set()
        self.special_init_inter_flows: Set[Tuple[int, int, int]] = set()
        self.magic_inter_flows: Set[Tuple[int, int, int]] = set()

        self.call_labels: Set[int] = set()
        self.return_labels: Set[int] = set()
        self.dummy_labels: Set[int] = set()

        self.is_generator: bool = False

    def _traverse(self, block: BasicBlock, visited: Set[int] = set()) -> None:
        if block.bid not in visited:
            visited.add(block.bid)
            additional = ""
            for id1, id2 in self.classdef_inter_flows:
                if id1 == block.bid:
                    additional += "Enter into the class"
                if id2 == block.bid:
                    additional += "Return from the class"

            for id1, id2, id3 in self.setter_inter_flows:
                if id1 == block.bid:
                    additional += "Call descriptor setter"
                if id2 == block.bid:
                    additional += "Return from descriptor setter"
                if id3 == block.bid:
                    additional += "Dummy return from descriptor setter"

            for id1, id2, id3 in self.getter_inter_flows:
                if id1 == block.bid:
                    additional += "Call descriptor getter"
                if id2 == block.bid:
                    additional += "Return from descriptor getter"
                if id3 == block.bid:
                    additional += "Dummy return from descriptor getter"
            for id1, id2, id3 in self.magic_inter_flows:
                if id1 == block.bid:
                    additional += "Possibly invoke magic methods"
                if id2 == block.bid:
                    additional += "Possibly return of magic methods"
                if id3 == block.bid:
                    additional += "Dummy possibly return of magic methods"

            for (
                id1,
                id2,
                id3,
                id4,
                id5,
                id6,
                id7,
                id8,
                id9,
            ) in self.call_return_inter_flows:
                if id1 == block.bid:
                    additional += "Call label"
                if id2 == block.bid:
                    additional += "__new__ return label"
                if id3 == block.bid:
                    additional += "Dummy __new__ return label"
                # if id4 == block.bid:
                #     additional += "Call descriptor getter"
                # if id5 == block.bid:
                #     additional += "Return from descriptor getter"
                # if id6 == block.bid:
                #     additional += "Dummy return from descriptor getter"
                if id7 == block.bid:
                    additional += "__init__ call label"
                if id8 == block.bid:
                    additional += "Return label"
                if id9 == block.bid:
                    additional += "Dummy return label"
            self.graph.node(str(block.bid), label=block.stmt_to_code() + additional)
            for next_bid in block.next:
                self._traverse(self.blocks[next_bid], visited)
                self.graph.edge(
                    str(block.bid),
                    str(next_bid),
                    label=astor.to_source(self.edges[(block.bid, next_bid)])
                    if self.edges[(block.bid, next_bid)]
                    else "",
                )

    def generate(self, fmt: str, name: str) -> gv.dot.Digraph:
        self.graph = gv.Digraph(name="cluster_" + str(self.start_block.bid), format=fmt)
        self.graph.attr(label=name)
        self._traverse(self.start_block)
        for lab, cfg in self.sub_cfgs.items():
            self.graph.subgraph(cfg.generate(fmt, "CFG at label {}".format(lab)))
        return self.graph

    def show(
        self,
        filepath: str = "output",
        fmt: str = "png",
        show: bool = True,
        name: str = None,
    ) -> None:
        self.generate(fmt, name)
        path = os.path.normpath(filepath)
        self.graph.render(path, view=show, cleanup=True)


class CFGVisitor(ast.NodeVisitor):
    def __init__(
        self,
        entry_node=ast.Pass(),
    ):
        super().__init__()
        self.cfg: Optional[CFG] = None
        self.curr_block: Optional[BasicBlock] = None
        self.parent_node = entry_node
        self.after_loop_stack: List[BasicBlock] = []
        self.loop_guard_stack: List[BasicBlock] = []
        self.final_body_entry_stack: List[BasicBlock] = []
        self.final_body_exit_stack: List[BasicBlock] = []
        self.properties: Dict = defaultdict(lambda: [None] * 4)
        # check if a function is a generator function by checking if it has yields
        self.is_generator: bool = False

    def build(self, name: str, tree: ast.Module) -> CFG:
        self.cfg = CFG(name)
        self.curr_block = self.new_block()
        self.visit(tree)
        self.remove_empty_blocks(self.cfg.start_block, set())
        self.refactor_flows_and_labels()
        return self.cfg

    def new_block(self) -> BasicBlock:
        bid: int = BlockId.gen_block_id()
        self.cfg.blocks[bid] = BasicBlock(bid)
        return self.cfg.blocks[bid]

    def add_edge(self, frm_id: int, to_id: int, condition=None) -> BasicBlock:
        if to_id in self.cfg.blocks[frm_id].next:
            pass
            # assert False, f"{frm_id}, {to_id}"
        else:
            self.cfg.blocks[frm_id].next.append(to_id)

        if frm_id in self.cfg.blocks[to_id].prev:
            pass
            # assert False, f"{frm_id}, {to_id}"
        else:
            self.cfg.blocks[to_id].prev.append(frm_id)

        self.cfg.edges[(frm_id, to_id)] = condition
        return self.cfg.blocks[to_id]

    def add_loop_block(self) -> BasicBlock:
        if self.curr_block.is_empty() and not self.curr_block.has_next():
            return self.curr_block
        else:
            loop_block = self.new_block()
            return self.add_edge(self.curr_block.bid, loop_block.bid)

    def add_FuncCFG(self, tree: ast.FunctionDef) -> None:
        func_id = self.curr_block.bid
        visitor: CFGVisitor = CFGVisitor(
            entry_node=self.curr_block.stmt[0].args,
        )
        func_cfg: CFG = visitor.build(tree.name, ast.Module(body=tree.body))

        if visitor.is_generator:
            func_cfg.is_generator = True

        self.cfg.sub_cfgs[func_id] = func_cfg

    def add_ClassCFG(self, node: ast.ClassDef):

        class_id = self.curr_block.bid
        visitor: CFGVisitor = CFGVisitor()
        class_cfg: CFG = visitor.build(node.name, ast.Module(body=node.body))
        self.cfg.sub_cfgs[class_id] = class_cfg

    def remove_empty_blocks(self, block: BasicBlock, visited: Set[int]) -> None:
        if block.bid not in visited:
            visited.add(block.bid)
            if block.is_empty():
                for prev_bid in list(block.prev):
                    prev_block = self.cfg.blocks[prev_bid]
                    for next_bid in list(block.next):
                        next_block = self.cfg.blocks[next_bid]
                        self.add_edge(prev_bid, next_bid)
                        self.cfg.edges.pop((block.bid, next_bid), None)
                        next_block.remove_from_prev(block.bid)
                    self.cfg.edges.pop((prev_bid, block.bid), None)
                    prev_block.remove_from_next(block.bid)

                block.prev.clear()
                for next_bid in list(block.next):
                    self.remove_empty_blocks(self.cfg.blocks[next_bid], visited)
                block.next.clear()

            else:
                for next_bid in list(block.next):
                    self.remove_empty_blocks(self.cfg.blocks[next_bid], visited)

    def refactor_flows_and_labels(self):
        for fst_id, snd_id in self.cfg.edges:
            self.cfg.flows.add((fst_id, snd_id))

        for (
            l1,
            l2,
            dummy,
            init,
            init_return,
            init_dummy_return,
            l4,
            l5,
            dummy2,
        ) in self.cfg.call_return_inter_flows:
            self.cfg.flows -= {(l1, l2), (l4, l5)}
            self.cfg.call_labels.update({l1, l4})
            self.cfg.return_labels.update({l2, l5})
        for l1, l2 in self.cfg.classdef_inter_flows:
            self.cfg.flows -= {(l1, l2)}
            self.cfg.call_labels.add(l1)
            self.cfg.return_labels.add(l2)
        for l1, l2, dummy in self.cfg.setter_inter_flows:
            self.cfg.flows -= {(l1, l2)}
            self.cfg.call_labels.add(l1)
            self.cfg.return_labels.add(l2)
        for l1, l2, dummy in self.cfg.getter_inter_flows:
            self.cfg.flows -= {(l1, l2)}
            self.cfg.call_labels.add(l1)
            self.cfg.return_labels.add(l2)
        for l1, l2, dummy in self.cfg.magic_inter_flows:
            self.cfg.flows -= {(l1, l2)}
            self.cfg.call_labels.add(l1)
            self.cfg.return_labels.add(l2)

    def combine_conditions(self, node_list: List[ast.expr]) -> ast.expr:
        return (
            node_list[0]
            if len(node_list) == 1
            else ast.BoolOp(op=ast.And(), values=node_list)
        )

    def populate_body(self, body_list):
        for child in body_list:
            self.visit(child)

    def populate_body_to_next_bid(self, body_list, to_bid: int) -> None:
        for child in body_list:
            self.visit(child)
        if not self.curr_block.next:
            self.add_edge(self.curr_block.bid, to_bid)

    def visit_Module(self, node: ast.Module) -> None:
        # pre structure cleaning
        self.cfg.start_block = self.curr_block
        add_stmt(self.cfg.start_block, self.parent_node)
        self.cfg.final_block = self.new_block()
        add_stmt(self.cfg.final_block, ast.Pass())

        self.curr_block = self.add_edge(self.curr_block.bid, self.new_block().bid)
        self.generic_visit(node)
        # re-construct properties
        self._unify_properties()

        # post structure cleaning
        self.add_edge(self.curr_block.bid, self.cfg.final_block.bid)

    def _unify_properties(self):
        for name, attrs in self.properties.items():
            new_attrs = []
            for attr in attrs:
                if isinstance(attr, str):
                    new_attrs.append(ast.Name(id=attr))
                else:
                    assert attr is None, attr
                    new_attrs.append(ast.NameConstant(value=None))

            property_assign = ast.Assign(
                targets=[ast.Name(id=name)],
                value=ast.Call(
                    func=ast.Name(id=property.__name__), args=new_attrs, keywords=[]
                ),
            )
            self.visit(property_assign)

    def _check_decorator_list(self, node: ast.FunctionDef):
        if not node.decorator_list:
            return

        if len(node.decorator_list) > 1:
            raise NotImplementedError

        decorator = node.decorator_list[0]
        # @property
        if isinstance(decorator, ast.Name) and decorator.id == property.__name__:
            self.properties[node.name][0] = node.name
            node.decorator_list = []
        elif isinstance(decorator, ast.Attribute):
            # @xxx.setter
            if decorator.attr == property.setter.__name__:
                tmp_func_name = TempVariableName.generate()
                node.name = tmp_func_name
                self.properties[decorator.value.id][1] = node.name
                node.decorator_list = []
            # @xxx.deleter
            elif decorator.attr == property.deleter.__name__:
                tmp_func_name = TempVariableName.generate()
                node.name = tmp_func_name
                self.properties[decorator.value.id][2] = node.name
                node.decorator_list = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_decorator_list(node)

        decorator_list = node.decorator_list
        node.decorator_list = []

        # deal with node.arguments
        seq = self.visit_arguments(node.args)
        self.populate_body(seq)

        add_stmt(self.curr_block, node)
        self.add_FuncCFG(node)
        self.curr_block = self.add_edge(self.curr_block.bid, self.new_block().bid)

        self.visit_DecoratorList(node, decorator_list)

    def visit_DecoratorList(self, node: ast.FunctionDef | ast.ClassDef, decorator_list):
        stmt_sequence = []
        targets = [ast.Name(id=node.name)]
        for decorator in reversed(decorator_list):
            make_decorator = ast.Call(func=decorator, args=targets, keywords=[])
            stmt_sequence.append(ast.Assign(targets=targets, value=make_decorator))
        self.populate_body(stmt_sequence)

    def visit_arguments(self, node: ast.arguments) -> Any:
        seq = []

        # defaults args
        defaults: List[ast.expr] = node.defaults
        for idx, expr in enumerate(defaults):
            seq1, defaults[idx] = self.decompose_expr(expr)
            seq.extend(seq1)

        # kw_defaults args
        kw_defaults: List[ast.expr] = node.kw_defaults
        for idx, expr in enumerate(kw_defaults):
            seq1, kw_defaults[idx] = self.decompose_expr(expr)
            seq.extend(seq1)

        return seq

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        decorator_list = node.decorator_list
        node.decorator_list = []

        call_block = self.curr_block
        add_stmt(call_block, node)

        self.add_ClassCFG(node)

        return_block = self.add_edge(call_block.bid, self.new_block().bid)
        add_stmt(return_block, node)

        self.cfg.classdef_inter_flows.add((call_block.bid, return_block.bid))
        self.curr_block = self.add_edge(return_block.bid, self.new_block().bid)
        self.visit_DecoratorList(node, decorator_list)

    def visit_Return(self, node: ast.Return) -> None:
        if node.value is None:
            node.value = ast.NameConstant(value=None)
        seq, node.value = self.decompose_expr(node.value)
        self.populate_body(seq)
        add_stmt(self.curr_block, node)

        if self.final_body_entry_stack and self.final_body_exit_stack:
            self.add_edge(self.curr_block.bid, self.final_body_entry_stack[-1].bid)
            self.add_edge(self.final_body_exit_stack[-1].bid, self.cfg.final_block.bid)
        else:
            self.add_edge(self.curr_block.bid, self.cfg.final_block.bid)
        self.curr_block = self.new_block()

    def visit_Delete(self, node: ast.Delete) -> None:
        for target in node.targets:
            decomposed_expr_sequence = self.visit(target)
            delete_node = ast.Delete(targets=decomposed_expr_sequence[-1:])
            decomposed_expr_sequence = decomposed_expr_sequence[:-1]
            self.populate_body(decomposed_expr_sequence)
            add_stmt(self.curr_block, delete_node)
            self.curr_block = self.add_edge(self.curr_block.bid, self.new_block().bid)

    def visit_Assign(self, node: ast.Assign) -> None:

        new_expr_sequence = self.visit(node.value)

        if len(new_expr_sequence) == 1:
            if isinstance(node.value, ast.Call):
                # call node(implicit __new__)
                call_node = self.curr_block
                add_stmt(call_node, node.value)

                # __new__ return node
                new_node = self.add_edge(call_node.bid, self.new_block().bid)
                new_var = ast.Name(id=TempVariableName.generate())
                add_stmt(new_node, new_var)

                # __new__ dummy return node
                dummy_new_node = self.add_edge(new_node.bid, self.new_block().bid)
                add_stmt(dummy_new_node, new_var)
                self.cfg.dummy_labels.add(dummy_new_node.bid)

                # __init__ attr lookup node
                init_attribute_node = self.add_edge(
                    dummy_new_node.bid, self.new_block().bid
                )
                add_stmt(
                    init_attribute_node, ast.Attribute(value=new_var, attr="__init__")
                )

                # __init__ attr assigned
                init_attribute_assign_node = self.add_edge(
                    init_attribute_node.bid, self.new_block().bid
                )
                init_attribute_name = ast.Name(id=TempVariableName.generate())
                add_stmt(init_attribute_assign_node, init_attribute_name)

                # __init__ attr dummy assigned
                init_attribute_assign_node_dummy = self.add_edge(
                    init_attribute_assign_node.bid, self.new_block().bid
                )
                self.cfg.dummy_labels.add(init_attribute_assign_node_dummy.bid)
                add_stmt(init_attribute_assign_node_dummy, init_attribute_name)

                # __init__ call node
                init_call_node = self.add_edge(
                    init_attribute_assign_node_dummy.bid, self.new_block().bid
                )
                init_call = ast.Call(
                    func=init_attribute_name,
                    args=node.value.args,
                    keywords=node.value.keywords,
                )
                add_stmt(init_call_node, init_call)

                # __init__ return node
                init_return_node = self.add_edge(
                    init_call_node.bid, self.new_block().bid
                )
                init_var = ast.Name(id=TempVariableName.generate())
                add_stmt(init_return_node, init_var)

                # __init__ dummy return node(return node)
                dummy_return_node = self.add_edge(
                    init_return_node.bid, self.new_block().bid
                )
                add_stmt(dummy_return_node, init_var)
                self.cfg.dummy_labels.add(dummy_return_node.bid)

                # update call return flow
                self.cfg.call_return_inter_flows.add(
                    (
                        call_node.bid,
                        new_node.bid,
                        dummy_new_node.bid,
                        init_attribute_node.bid,
                        init_attribute_assign_node.bid,
                        init_attribute_assign_node_dummy.bid,
                        init_call_node.bid,
                        init_return_node.bid,
                        dummy_return_node.bid,
                    )
                )
                # update __new__ flow
                self.cfg.special_init_inter_flows.add(
                    (init_call_node.bid, init_return_node.bid, dummy_return_node.bid)
                )
                self.cfg.getter_inter_flows.add(
                    (
                        init_attribute_node.bid,
                        init_attribute_assign_node.bid,
                        init_attribute_assign_node_dummy.bid,
                    )
                )
                node.value = init_var
                self.curr_block = dummy_return_node
            else:
                # call x.y
                temp_return_name = ast.Name(id=TempVariableName.generate())

                call_node = self.curr_block
                add_stmt(call_node, node.value)

                # return xxx
                return_node = self.add_edge(call_node.bid, self.new_block().bid)
                add_stmt(return_node, temp_return_name)
                # dummy xxx
                dummy_return_node = self.add_edge(return_node.bid, self.new_block().bid)
                add_stmt(dummy_return_node, temp_return_name)

                self.cfg.dummy_labels.add(dummy_return_node.bid)

                if isinstance(node.value, ast.Attribute):
                    # update attribute info
                    self.cfg.getter_inter_flows.add(
                        (call_node.bid, return_node.bid, dummy_return_node.bid)
                    )
                else:
                    # update atribute info
                    self.cfg.magic_inter_flows.add(
                        (call_node.bid, return_node.bid, dummy_return_node.bid)
                    )
                node.value = temp_return_name
                self.curr_block = dummy_return_node
            self.curr_block = self.add_edge(self.curr_block.bid, self.new_block().bid)

            for target in node.targets:
                if isinstance(target, ast.Name):
                    tmp_assign = ast.Assign(targets=[target], value=node.value)
                    add_stmt(self.curr_block, tmp_assign)
                    self.curr_block = self.add_edge(
                        self.curr_block.bid, self.new_block().bid
                    )
                elif isinstance(target, ast.Attribute):
                    assert isinstance(target.value, ast.Name)
                    tmp_assign = ast.Assign(targets=[target], value=node.value)
                    call_node = self.curr_block
                    add_stmt(call_node, tmp_assign)

                    return_node = self.add_edge(call_node.bid, self.new_block().bid)
                    add_stmt(return_node, tmp_assign)

                    dummy_return_node = self.add_edge(
                        return_node.bid, self.new_block().bid
                    )
                    add_stmt(dummy_return_node, tmp_assign)

                    self.cfg.dummy_labels.add(dummy_return_node.bid)
                    self.cfg.setter_inter_flows.add(
                        (call_node.bid, return_node.bid, dummy_return_node.bid)
                    )
                    self.curr_block = dummy_return_node
                    self.curr_block = self.add_edge(
                        self.curr_block.bid, self.new_block().bid
                    )

                elif isinstance(target, ast.Subscript):
                    assert isinstance(target.value, ast.Name)
                    decomposed_slice_expr, target.slice = self.decompose_expr(
                        target.slice
                    )
                    self.populate_body(decomposed_slice_expr)
                    tmp_assign = ast.Assign(targets=[target], value=node.value)
                    add_stmt(self.curr_block, tmp_assign)
                    self.curr_block = self.add_edge(
                        self.curr_block.bid, self.new_block().bid
                    )
                elif isinstance(target, (ast.List, ast.Tuple)):
                    # we should not decompose elts in containers
                    expr_sequence = []
                    for idx, elt in enumerate(target.elts):
                        *decompose_expr, target.elts[idx] = self.visit(elt)
                        expr_sequence.extend(decompose_expr)
                    self.populate_body(expr_sequence)
                    tmp_assign = ast.Assign(targets=[target], value=node.value)
                    add_stmt(self.curr_block, tmp_assign)
                    self.curr_block = self.add_edge(
                        self.curr_block.bid, self.new_block().bid
                    )
                elif isinstance(target, ast.Starred):
                    raise NotImplementedError
            return

        new_assign = ast.Assign(targets=node.targets, value=new_expr_sequence[-1])
        new_sequence: List = new_expr_sequence[:-1] + [new_assign]
        if isinstance(node.value, (ast.ListComp, ast.SetComp, ast.DictComp)):
            new_sequence.append(
                ast.Delete(
                    targets=[ast.Name(id=new_expr_sequence[-1].id, ctx=ast.Del())]
                )
            )
        self.populate_body(new_sequence)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        # We are only interested in types, so transform AugAssign into Assign

        assign = ast.Assign(
            targets=[node.target],
            value=ast.BinOp(left=node.target, op=node.op, right=node.value),
        )
        self.visit(assign)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value:
            decomposed, node.value = self.decompose_expr(node.value)
            self.populate_body(decomposed)
            add_stmt(self.curr_block, node)
            self.curr_block = self.add_edge(self.curr_block.bid, self.new_block().bid)

    def visit_For(self, node: ast.For) -> None:
        iter_call: ast.Call = ast.Call(
            args=[node.iter], func=ast.Name(id="iter", ctx=ast.Load()), keywords=[]
        )
        iter_seq: List = self.visit(iter_call)

        iter_name = ast.Name(id=TempVariableName.generate())
        new_assign = ast.Assign(
            targets=[iter_name],
            value=iter_seq[-1],
        )

        iter_seq = iter_seq[:-1] + [new_assign]

        new_while: ast.While = ast.While(
            test=iter_name,
            body=[
                ast.Assign(
                    targets=[node.target],
                    value=ast.Call(
                        func=ast.Name(id="next"), args=[iter_name], keywords=[]
                    ),
                )
            ]
            + node.body,
            orelse=node.orelse,
        )
        iter_seq.append(new_while)
        iter_seq.append(ast.Delete(targets=[iter_name]))
        self.populate_body(iter_seq)

    def visit_While(self, node: ast.While) -> None:

        test_sequence, node.test = self.decompose_expr(node.test)
        self.populate_body(test_sequence)

        loop_guard: BasicBlock = self.add_loop_block()
        self.curr_block = loop_guard
        add_stmt(loop_guard, node)
        self.loop_guard_stack.append(loop_guard)

        # New block for the case where the test in the while is False.
        after_while_block: BasicBlock = self.new_block()
        self.add_edge(self.curr_block.bid, after_while_block.bid)
        self.after_loop_stack.append(after_while_block)

        if not node.orelse:
            # New block for the case where the test in the while is True.
            # Populate the while block.
            while_body_block: BasicBlock = self.new_block()
            self.add_edge(self.curr_block.bid, while_body_block.bid)
            self.curr_block = while_body_block

            self.populate_body_to_next_bid(node.body, loop_guard.bid)
        else:
            or_else_block: BasicBlock = self.new_block()
            self.add_edge(self.curr_block.bid, or_else_block.bid)
            self.curr_block = self.add_edge(self.curr_block.bid, self.new_block().bid)
            self.populate_body_to_next_bid(node.body, loop_guard.bid)

            self.curr_block = or_else_block
            self.populate_body_to_next_bid(node.orelse, after_while_block.bid)

        # Continue building the CFG in the after-while block.
        self.curr_block = after_while_block
        self.after_loop_stack.pop()
        self.loop_guard_stack.pop()

    def visit_If(self, node: ast.If) -> None:
        test_sequence, node.test = self.decompose_expr(node.test)
        self.populate_body(test_sequence)

        # Add the If statement at the end of the current block.
        add_stmt(self.curr_block, node)

        # Create a block for the code after the if-else.
        after_if_block: BasicBlock = self.new_block()

        # Create a new block for the body of the if.
        if_body_block: BasicBlock = self.add_edge(
            self.curr_block.bid, self.new_block().bid
        )

        # New block for the body of the else if there is an else clause.
        if node.orelse:
            self.curr_block = self.add_edge(self.curr_block.bid, self.new_block().bid)

            # Visit the children in the body of the else to populate the block.
            self.populate_body_to_next_bid(node.orelse, after_if_block.bid)
        else:
            self.add_edge(self.curr_block.bid, after_if_block.bid)
        # Visit children to populate the if block.
        self.curr_block: BasicBlock = if_body_block
        self.populate_body_to_next_bid(node.body, after_if_block.bid)

        # Continue building the CFG in the after-if block.
        self.curr_block: BasicBlock = after_if_block

    def visit_With(self, node: ast.With) -> None:
        # https: // docs.python.org / zh - cn / 3.12 / reference / compound_stmts.html

        if len(node.items) > 1:
            curr_body = node.body
            for item in reversed(node.items[1:]):
                item_with = ast.With(items=[item], body=curr_body)
                curr_body = [item_with]
            node.items = node.items[0:1]
            node.body = curr_body
            self.visit(node)
        else:
            manager_var = ast.Name(id=TempVariableName.generate())
            manager_assign = ast.Assign(
                targets=[manager_var], value=node.items[0].context_expr
            )
            manager_type_var = ast.Name(id=TempVariableName.generate())
            manager_type_value = ast.Call(
                func=ast.Name(id="type"), args=[manager_var], keywords=[]
            )
            manager_type_assign = ast.Assign(
                targets=[manager_type_var], value=manager_type_value
            )
            enter_var = ast.Name(id=TempVariableName.generate())
            enter_value = ast.Attribute(
                value=manager_type_var,
                attr="__enter__",
                ctx=ast.Load(),
            )
            enter_assign = ast.Assign(targets=[enter_var], value=enter_value)
            exit_var = ast.Name(id=TempVariableName.generate())
            exit_value = ast.Attribute(
                value=manager_type_var,
                attr="__exit__",
                ctx=ast.Load(),
            )
            exit_assign = ast.Assign(targets=[exit_var], value=exit_value)
            value_var = ast.Name(id=TempVariableName.generate())
            value_value = ast.Call(func=enter_var, args=[manager_var], keywords=[])
            value_assign = ast.Assign(targets=[value_var], value=value_value)
            preceded = [
                manager_assign,
                manager_type_assign,
                enter_assign,
                exit_assign,
                value_assign,
            ]
            if node.items[0].optional_vars is not None:
                preceded.append(
                    ast.Assign(targets=[node.items[0].optional_vars], value=value_var)
                )
            new_expr_sequence = (
                preceded
                + node.body
                + [
                    ast.Call(
                        func=exit_var, args=[manager_var, None, None, None], keywords=[]
                    )
                ]
            )
            self.populate_body(new_expr_sequence)

    # Need to record exception handling stack
    def visit_Raise(self, node: ast.Raise) -> None:
        if self.final_body_entry_stack and self.final_body_exit_stack:
            return_as_raise = ast.Return(value=None)
            self.visit(return_as_raise)
        else:
            pass_as_raise = ast.Pass()
            self.visit(pass_as_raise)

    def visit_Try(self, node: ast.Try) -> None:
        if not node.orelse:
            node.orelse = []
        if not node.finalbody:
            node.finalbody = []

        # stage curr_block
        try_body_entry_block = self.curr_block
        after_try_block = self.new_block()

        # deal with finalbody
        final_body_entry_block = self.new_block()
        add_stmt(final_body_entry_block, ast.Pass())
        final_body_exit_block = self.new_block()
        add_stmt(final_body_exit_block, ast.Pass())
        self.curr_block = self.add_edge(
            final_body_entry_block.bid, self.new_block().bid
        )
        self.populate_body_to_next_bid(node.finalbody, final_body_exit_block.bid)
        self.add_edge(final_body_exit_block.bid, after_try_block.bid)

        self.final_body_entry_stack.append(final_body_entry_block)
        self.final_body_exit_stack.append(final_body_exit_block)

        # deal with orelse
        orelse_body_entry_block = self.new_block()
        add_stmt(orelse_body_entry_block, ast.Pass())
        orelse_body_exit_block = self.new_block()
        add_stmt(orelse_body_exit_block, ast.Pass())
        self.curr_block = self.add_edge(
            orelse_body_entry_block.bid, self.new_block().bid
        )
        self.populate_body_to_next_bid(node.orelse, orelse_body_exit_block.bid)
        self.add_edge(orelse_body_exit_block.bid, final_body_entry_block.bid)

        # deal with try body
        self.curr_block = try_body_entry_block
        self.populate_body_to_next_bid(node.body, orelse_body_entry_block.bid)

        self.final_body_entry_stack.pop()
        self.final_body_exit_stack.pop()

        self.curr_block = after_try_block

    # If assert fails, AssertionError will be raised.
    # If assert succeeds, execute normal flow.
    def visit_Assert(self, node):
        new_if: ast.If = ast.If(
            test=ast.UnaryOp(op=ast.Not(), operand=node.test),
            body=[
                ast.Raise(exc=ast.Name(id="AssertionError", ctx=ast.Load()), cause=None)
            ]
            if node.msg is None
            else [
                ast.Raise(
                    exc=ast.Call(
                        args=[node.msg],
                        func=ast.Name(id="AssertionError", ctx=ast.Load()),
                        keywords=[],
                    ),
                    cause=None,
                )
            ],
            orelse=[],
        )
        self.visit(new_if)

    def visit_Import(self, node: ast.Import) -> None:
        for name in node.names:
            # call node
            call_node = self.curr_block
            single_import: ast.Import = ast.Import(names=[name])
            add_stmt(call_node, single_import)
            # the node after return node
            self.curr_block = self.add_edge(call_node.bid, self.new_block().bid)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        call_node = self.curr_block
        add_stmt(call_node, node)
        self.curr_block = self.add_edge(call_node.bid, self.new_block().bid)

    def visit_Global(self, node: ast.Global) -> None:
        for name in node.names:
            single_global = ast.Global(names=[name])
            add_stmt(self.curr_block, single_global)
            self.curr_block = self.add_edge(self.curr_block.bid, self.new_block().bid)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        for name in node.names:
            single_nonlocal = ast.Nonlocal(names=[name])
            add_stmt(self.curr_block, single_nonlocal)
            self.curr_block = self.add_edge(self.curr_block.bid, self.new_block().bid)

    def visit_Expr(self, node: ast.Expr) -> None:

        tmp_var = TempVariableName.generate()
        tmp_assign = ast.Assign(
            targets=[ast.Name(id=tmp_var, ctx=ast.Store())], value=node.value
        )
        self.visit(tmp_assign)

    def visit_Pass(self, node: ast.Pass) -> None:
        add_stmt(self.curr_block, node)
        self.curr_block = self.add_edge(self.curr_block.bid, self.new_block().bid)

    def visit_Break(self, node: ast.Break) -> None:
        add_stmt(self.curr_block, node)

        if self.final_body_entry_stack and self.final_body_exit_stack:
            self.add_edge(self.curr_block.bid, self.final_body_entry_stack[-1].bid)
            self.add_edge(self.curr_block.bid, self.final_body_exit_stack[-1].bid)
            self.add_edge(
                self.final_body_exit_stack[-1].bid, self.after_loop_stack[-1].bid
            )
        else:
            self.add_edge(self.curr_block.bid, self.after_loop_stack[-1].bid)

    def visit_Continue(self, node: ast.Continue) -> None:
        add_stmt(self.curr_block, node)
        # continue in a try block
        if self.final_body_entry_stack:
            self.add_edge(self.curr_block.bid, self.final_body_entry_stack[-1].bid)
        else:
            self.add_edge(self.curr_block.bid, self.loop_guard_stack[-1].bid)

    ################################################################
    ################################################################
    # expr
    # For now I think there are several basic types in Python.
    # ast.Num, such as 1
    # ast.Str, such as 'jojo'
    # ast.FormattedValue inside JoinedStr, note that I didn't come across a case that it was alone
    # ast.JoinedStr, such as f'{a}'
    # ast.Bytes, such as b'a'
    # ast.NameConstant, such as True
    # ast.Ellipsis, it's ...
    # ast.Constant, I didn't know how it would be used in python 3.7
    # ast.Name, a name represents a value evaluated.
    #
    # We care about these basic types since we need some criterion to stop recursion of expanding expressions.
    #

    # decompose a single expression.
    # new_expr_sequence stores a list of temporal statements
    # decompose_expr(expr)-> List[expr], ast.Name

    # self.visit(expr) returns destructed expr. and the last element is simplified expr itself.

    def decompose_expr(self, expr: ast.expr) -> Tuple:
        if expr is None:
            return [], None
        seq = self.visit(expr)
        if not isinstance(seq[-1], ast.Name):
            tmp_var = TempVariableName.generate()
            ast_assign = ast.Assign(
                targets=[ast.Name(id=tmp_var, ctx=ast.Store())],
                value=seq[-1],
            )
            ast_name = ast.Name(id=tmp_var, ctx=ast.Load())
            seq = seq[:-1] + [ast_assign]
            return seq, ast_name
        else:
            return seq[:-1], seq[-1]

    ################################################################
    ################################################################
    # a and b and c
    # tmp = a, tmp = b, tmp = c
    # tmp = a
    # if a:
    #   tmp = b
    #   if b:
    #     tmp=c
    def visit_BoolOp(self, node: ast.BoolOp) -> Any:
        new_var: str = TempVariableName.generate()
        assign_list = [
            ast.Assign(targets=[ast.Name(id=new_var, ctx=ast.Store())], value=value)
            for value in node.values
        ]
        current_sequence = assign_list[-1:]
        for assign in reversed(assign_list[:-1]):
            tmp_if = ast.If(
                test=assign.value
                if isinstance(node.op, ast.And)
                else ast.UnaryOp(op=ast.Not(), operand=assign.value),
                body=current_sequence,
                orelse=[],
            )
            current_sequence = [assign, tmp_if]

        return current_sequence + [ast.Name(id=new_var, ctx=ast.Load())]

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        seq1, node.left = self.decompose_expr(node.left)
        seq2, node.right = self.decompose_expr(node.right)

        return seq1 + seq2 + [node]

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        seq, node.operand = self.decompose_expr(node.operand)

        return seq + [node]

    def visit_Lambda(self, node: ast.Lambda) -> Any:
        tmp_var = TempVariableName.generate()

        seq_args = self.visit_arguments(node.args)
        seq_ret, name = self.decompose_expr(node.body)

        tmp_function_def = ast.FunctionDef(
            name=tmp_var,
            args=node.args,
            body=seq_ret + [ast.Return(name)],
            decorator_list=[],
            returns=None,
        )
        tmp_function_name = ast.Name(id=tmp_var, ctx=ast.Load())

        return seq_args + [tmp_function_def, tmp_function_name]

    def visit_IfExp(self, node: ast.IfExp) -> Any:
        tmp_var: str = TempVariableName.generate()
        tmp_name: ast.Name = ast.Name(id=tmp_var, ctx=ast.Store())
        new_if: ast.If = ast.If(
            test=node.test,
            body=[ast.Assign(targets=[tmp_name], value=node.body)],
            orelse=[ast.Assign(targets=[tmp_name], value=node.orelse)],
        )

        return [new_if, tmp_name]

    def visit_Dict(self, node: ast.Dict) -> Any:
        seq = []
        for idx, key in enumerate(node.keys):
            seq1, node.keys[idx] = self.decompose_expr(key)
            seq.extend(seq1)
            seq1, node.values[idx] = self.decompose_expr(node.values[idx])
            seq.extend(seq1)

        return seq + [node]

    def visit_Set(self, node: ast.Set) -> Any:
        seq = []
        for idx, elt in enumerate(node.elts):
            seq1, node.elts[idx] = self.decompose_expr(elt)
            seq.extend(seq1)
        return seq + [node]

    def visit_ListComp(self, node: ast.ListComp) -> Any:

        new_expr_sequence = []
        listcomp_var = TempVariableName.generate()
        new_expr_sequence.append(
            ast.Assign(
                targets=[ast.Name(id=listcomp_var, ctx=ast.Store())],
                value=ast.List(elts=[], ctx=ast.Load()),
            )
        )
        new_expr_sequence += self._visit_ListComp(
            listcomp_var, node.elt, node.generators
        )
        new_expr_sequence.append(ast.Name(id=listcomp_var, ctx=ast.Load()))
        return new_expr_sequence

    def _visit_ListComp(
        self, listcomp_var: str, elt: ast.expr, generators: List[ast.comprehension]
    ) -> Any:
        if not generators:
            tmp_call = ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id=listcomp_var, ctx=ast.Load()),
                    attr="append",
                    ctx=ast.Load(),
                ),
                args=[elt],
                keywords=[],
            )
            seq, name = self.decompose_expr(elt)
            tmp_call.args = [name]

            seq.append(ast.Expr(value=tmp_call))
            return seq
        else:
            return [
                ast.For(
                    target=generators[0].target,
                    iter=generators[0].iter,
                    body=[
                        ast.If(
                            test=self.combine_conditions(generators[0].ifs),
                            body=self._visit_ListComp(
                                listcomp_var, elt, generators[1:]
                            ),
                            orelse=[],
                        )
                    ]
                    if generators[0].ifs
                    else self._visit_ListComp(listcomp_var, elt, generators[1:]),
                    orelse=[],
                )
            ]

    def visit_SetComp(self, node: ast.SetComp) -> Any:
        new_expr_sequence = []
        setcomp_var = TempVariableName.generate()
        new_expr_sequence.append(
            ast.Assign(
                targets=[ast.Name(id=setcomp_var, ctx=ast.Store())],
                value=ast.Call(
                    args=[], func=ast.Name(id="set", ctx=ast.Load()), keywords=[]
                ),
            )
        )
        new_expr_sequence += self._visit_SetComp(setcomp_var, node.elt, node.generators)
        new_expr_sequence.append(ast.Name(id=setcomp_var, ctx=ast.Load()))
        return new_expr_sequence

    def _visit_SetComp(
        self, setcomp_var: str, elt: ast.expr, generators: List[ast.comprehension]
    ):
        if not generators:
            tmp_call = ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id=setcomp_var, ctx=ast.Load()),
                    attr="add",
                    ctx=ast.Load(),
                ),
                args=[elt],
                keywords=[],
            )
            seq, name = self.decompose_expr(elt)
            tmp_call.args = [name]
            seq.append(ast.Expr(value=tmp_call))
            return seq
        else:
            return [
                ast.For(
                    target=generators[0].target,
                    iter=generators[0].iter,
                    body=[
                        ast.If(
                            test=self.combine_conditions(generators[0].ifs),
                            body=self._visit_SetComp(setcomp_var, elt, generators[1:]),
                            orelse=[],
                        )
                    ]
                    if generators[0].ifs
                    else self._visit_SetComp(setcomp_var, elt, generators[1:]),
                    orelse=[],
                )
            ]

    def visit_DictComp(self, node: ast.DictComp) -> Any:
        new_expr_sequence = []
        dictcomp_var = TempVariableName.generate()
        new_expr_sequence.append(
            ast.Assign(
                targets=[ast.Name(id=dictcomp_var, ctx=ast.Store())],
                value=ast.Dict(keys=[], values=[]),
            )
        )
        new_expr_sequence += self._visit_DictComp(
            dictcomp_var, node.key, node.value, node.generators
        )
        new_expr_sequence.append(ast.Name(id=dictcomp_var, ctx=ast.Load()))
        return new_expr_sequence

    def _visit_DictComp(
        self, dictcomp_var: str, key: ast.expr, value: ast.expr, generators
    ):
        if not generators:
            tmp_index = ast.Index(value=key)
            seq1, name1 = self.decompose_expr(key)
            tmp_index.value = name1
            tmp_subscript = ast.Subscript(
                value=ast.Name(id=dictcomp_var, ctx=ast.Load()),
                slice=tmp_index,
                ctx=ast.Store(),
            )
            tmp_assign = ast.Assign(
                targets=[tmp_subscript],
                value=value,
            )
            seq2, name2 = self.decompose_expr(value)
            tmp_assign.value = name2

            return seq1 + seq2 + [tmp_assign]
        else:
            return [
                ast.For(
                    target=generators[0].target,
                    iter=generators[0].iter,
                    body=[
                        ast.If(
                            test=self.combine_conditions(generators[0].ifs),
                            body=self._visit_DictComp(
                                dictcomp_var, key, value, generators[1:]
                            ),
                            orelse=[],
                        )
                    ]
                    if generators[0].ifs
                    else self._visit_DictComp(dictcomp_var, key, value, generators[1:]),
                    orelse=[],
                )
            ]

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> Any:
        new_expr_sequence = []
        generator_var = TempVariableName.generate()
        new_expr_sequence.append(
            ast.FunctionDef(
                name=generator_var,
                args=ast.arguments(
                    args=[],
                    vararg=None,
                    kwonlyargs=[],
                    kw_defaults=[],
                    kwarg=None,
                    defaults=[],
                ),
                body=self._visit_GeneratorExp(node.elt, node.generators),
                decorator_list=[],
                returns=None,
            )
        )
        new_expr_sequence.append(
            ast.Call(
                func=ast.Name(id=generator_var, ctx=ast.Load()), args=[], keywords=[]
            )
        )
        return new_expr_sequence

    def _visit_GeneratorExp(self, elt: ast.expr, generators: List[ast.comprehension]):
        if not generators:
            tmp_yield = ast.Yield(value=elt)
            seq, name = self.decompose_expr(elt)
            tmp_yield.value = name
            seq.append(ast.Expr(value=tmp_yield))
            return seq
        else:
            return [
                ast.For(
                    target=generators[0].target,
                    iter=generators[0].iter,
                    body=[
                        ast.If(
                            test=self.combine_conditions(generators[0].ifs),
                            body=self._visit_GeneratorExp(elt, generators[1:]),
                            orelse=[],
                        )
                    ]
                    if generators[0].ifs
                    else self._visit_GeneratorExp(elt, generators[1:]),
                    orelse=[],
                )
            ]

    def visit_Yield(self, node: ast.Yield) -> Any:
        # encounter yield, this function is a generator function
        self.is_generator = True

        if node.value is None:
            node.value = ast.NameConstant(value=None)
            return [node]

        seq, node.value = self.decompose_expr(node.value)

        return seq + [node]

    def visit_YieldFrom(self, node: ast.YieldFrom) -> Any:
        # encounter yield from, this function is a generator function
        self.is_generator = True

        seq, node.value = self.decompose_expr(node.value)

        return seq + [node]

    def visit_Compare(self, node: ast.Compare) -> Any:
        seq = []
        names = []
        for expr in [node.left] + node.comparators:
            seq1, name1 = self.decompose_expr(expr)
            seq.extend(seq1)
            names.append(name1)

        node.left, node.comparators = names[0], names[1:]
        return seq + [node]

    def visit_Call(self, node: ast.Call) -> Any:
        if isinstance(node.func, ast.Lambda):
            raise NotImplementedError
            # seq1, name = self.decompose_expr(node.func)
            # tmp_call = ast.Call(args=node.args, func=name, keywords=node.keywords)
            # return seq1 + [tmp_call]

        seq = []

        # decompose func
        seq1, node.func = self.decompose_expr(node.func)
        seq.extend(seq1)

        # decompose args
        for idx, expr in enumerate(node.args):
            seq1, node.args[idx] = self.decompose_expr(expr)
            seq.extend(seq1)

        for idx, keyword in enumerate(node.keywords):
            seq1, keyword.value = self.decompose_expr(keyword.value)
            seq.extend(seq1)

        return seq + [node]

    def visit_Num(self, node: ast.Num) -> Any:
        return [node]

    def visit_Str(self, node: ast.Str) -> Any:
        return [node]

    def visit_FormattedValue(self, node: ast.FormattedValue) -> Any:
        seq = []

        # deal with node.value
        seq1, node.value = self.decompose_expr(node.value)
        seq.extend(seq1)

        # deal with node.format_spec
        if node.format_spec:
            seq1, node.format_spec = self.decompose_expr(node.format_spec)
            seq.extend(seq1)

        return seq + [node]

    def visit_JoinedStr(self, node: ast.JoinedStr) -> Any:
        seq = []
        for idx, value in enumerate(node.values):
            seq1, node.values[idx] = self.decompose_expr(value)
            seq.extend(seq1)
        return seq + [node]

    def visit_Bytes(self, node: ast.Bytes) -> Any:
        return [node]

    def visit_NameConstant(self, node: ast.NameConstant) -> Any:
        return [node]

    def visit_Ellipsis(self, node: ast.Ellipsis) -> Any:
        return [node]

    def visit_Constant(self, node: ast.Constant) -> Any:
        return [node]

    # x.y
    # -> tmp = x.y
    def visit_Attribute(self, node) -> Any:
        seq, node.value = self.decompose_expr(node.value)
        return seq + [node]

    def visit_Subscript(self, node: ast.Subscript) -> Any:
        seq = []
        seq1, node.value = self.decompose_expr(node.value)
        seq.extend(seq1)
        seq2, node.slice = self.decompose_expr(node.slice)
        seq.extend(seq2)
        return seq + [node]

    def visit_Starred(self, node) -> Any:
        seq, node.value = self.decompose_expr(node.value)
        return seq + [node]

    def visit_Name(self, node: ast.Name) -> Any:
        return [node]

    def visit_List(self, node: ast.List) -> Any:
        seq = []
        for idx, elt in enumerate(node.elts):
            seq1, node.elts[idx] = self.decompose_expr(elt)
            seq.extend(seq1)
        return seq + [node]

    def visit_Tuple(self, node: ast.Tuple) -> Any:
        return self.visit_List(node)

    def visit_Slice(self, node: ast.Slice) -> Any:
        seq = []
        seq1, node.lower = self.decompose_expr(node.lower)
        seq.extend(seq1)
        seq2, node.upper = self.decompose_expr(node.upper)
        seq.extend(seq2)
        seq3, node.step = self.decompose_expr(node.step)
        seq.extend(seq3)
        return seq + [node]

    def visit_ExtSlice(self, node: ast.ExtSlice) -> Any:
        raise NotImplementedError(node)

    def visit_Index(self, node: ast.Index) -> Any:
        seq, node.value = self.decompose_expr(node.value)
        return seq + [node]
