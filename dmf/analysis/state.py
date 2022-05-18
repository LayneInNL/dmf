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

from dmf.analysis.flow_util import ProgramPoint
from dmf.analysis.heap import Heap
from dmf.analysis.stack import Stack, Frame
from dmf.analysis.value import ClsType, Value


class State:
    def __init__(self, state: State = None, ns=None):
        if state is not None:
            self.stack: Stack = state.stack.copy()
            self.heap: Heap = state.heap.copy()
        elif ns is not None:
            # if state is None, it's the initial state
            self.stack: Stack = Stack()
            self.heap: Heap = Heap()
            frame: Frame = Frame(ns, None, ns, None)
            self.push_frame_to_stack(frame)
        else:
            assert False

    def __le__(self, other: State):
        return self.stack <= other.stack and self.heap <= other.heap

    def __iadd__(self, other: State):
        self.stack += other.stack
        self.heap += other.heap
        return self

    def __repr__(self):
        res = "Stack: "
        res += self.stack.__repr__()
        res += "\nHeap:"
        res += self.heap.__repr__()
        res += "\n"
        return res

    def add_heap_and_cls(self, heap_ctx: int, cls_obj: ClsType):
        self.heap.add_heap_and_cls(heap_ctx, cls_obj)

    def read_field_from_heap(self, heap_ctx: int, field: str):
        return self.heap.read_from_field(heap_ctx, field)

    def write_field_to_heap(self, heap_ctx: int, field: str, value: Value):
        self.heap.write_to_field(heap_ctx, field, value)

    def push_frame_to_stack(self, frame: Frame):
        self.stack.push_frame(frame)

    def pop_frame_from_stack(self):
        self.stack.pop_frame()

    def top_frame_on_stack(self):
        return self.stack.top_frame()

    def stack_contains(self, name):
        return name in self.top_frame_on_stack()

    def heap_contains(self, heap_context, field):
        return (heap_context, field) in self.heap

    def read_var_from_stack(self, var: str):
        return self.stack.read_var(var)

    def write_var_to_stack(self, var: str, value):
        self.stack.write_var(var, value)

    def stack_exec_in_new_ns(self):
        self.stack.next_ns()

    def copy(self):
        copied = State(self)
        return copied


STATE_BOT = "BOT"


def issubset_state(state1: State | STATE_BOT, state2: State | STATE_BOT):
    if state1 == STATE_BOT:
        return True

    if state2 == STATE_BOT:
        return False

    return state1 <= state2


def update_state(state1: State, state2: State | STATE_BOT):
    if state2 == STATE_BOT:
        return state1

    state1 += state2
    return state1


def compute_value_of_expr(program_point: ProgramPoint, expr: ast.expr, state: State):
    lab, ctx = program_point
    if isinstance(expr, ast.Num):
        value = Value()
        n = expr.n
        if isinstance(n, int):
            value.inject_int_type()
        else:
            assert False
        return value
    elif isinstance(expr, ast.NameConstant):
        value = Value()
        if expr.value is None:
            value.inject_none_type()
        else:
            value.inject_bool_type()
        return value
    elif isinstance(expr, (ast.Str, ast.JoinedStr)):
        value = Value()
        value.inject_str()
        return value
    elif isinstance(expr, ast.Bytes):
        value = Value()
        value.inject_byte()
        return value
    elif isinstance(expr, ast.Name):
        return state.read_var_from_stack(expr.id)
    elif isinstance(expr, ast.Attribute):
        pass
    elif isinstance(expr, ast.Call):
        if isinstance(expr.func, ast.Name):
            return compute_value_of_expr(program_point, expr.func, state)
        elif isinstance(expr.func, ast.Attribute):
            # instance_value = compute_value_of_expr(expr.func.value, state)
            # heaps = instance_value.extract_heap_types()
            # value = Value()
            # for hcontext, cls in heaps:
            #     attribute_value = state.read_field_from_heap(
            #         hcontext, cls, expr.func.attr
            #     )
            #     value += attribute_value()
            # return value
            pass
    elif isinstance(expr, (ast.Compare, ast.BoolOp)):
        value = Value()
        value.inject_bool(-1)
        return value
    elif isinstance(expr, ast.BinOp):
        # left_value = compute_value_of_expr(expr.left, state)
        # right_value = compute_value_of_expr(expr.right, state)
        # left_prims = left_value.extract_prim_types()
        # right_prims = right_value.extract_prim_types()
        # value = Value()
        pass
    elif isinstance(expr, ast.List):
        value = Value()
        value.inject_list(lab)
        return value
    else:
        assert False
