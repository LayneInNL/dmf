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

import dmf.share
from dmf.analysis.heap import analysis_heap
from dmf.analysis.stack import Stack, Frame
from dmf.analysis.value import ClsType, Value, InsType, FuncType, ListType, ModuleType
from dmf.log.logger import logger


class State:
    def __init__(self, state: State = None):
        if state is not None:
            self.stack: Stack = state.stack.copy()
        else:
            self.stack: Stack = Stack()

    def init_first_frame(
        self, f_locals=None, f_back=None, f_globals=None, f_builtins=None
    ):
        frame: Frame = Frame(
            f_locals=f_locals, f_back=f_back, f_globals=f_globals, f_builtins=f_builtins
        )
        self.push_frame_to_stack(frame)

    def __le__(self, other: State):
        return self.stack <= other.stack

    def __iadd__(self, other: State):
        self.stack += other.stack
        return self

    def __repr__(self):
        return self.stack.__repr__()

    def push_frame_to_stack(self, frame: Frame):
        self.stack.push_frame(frame)

    def pop_frame_from_stack(self) -> Frame:
        return self.stack.pop_frame()

    def top_frame_on_stack(self) -> Frame:
        return self.stack.top_frame()

    def top_frame_contains(self, name):
        return name in self.top_frame_on_stack()

    def read_var_from_stack(self, var: str, scope="local"):
        return self.stack.read_var(var, scope)

    def write_var_to_stack(self, var: str, value: Value, scope: str = "local"):
        self.stack.write_var(var, value, scope)

    def stack_exec_in_new_ns(self):
        self.stack.next_ns()

    def check_module_diff(self, new_module_name=None):
        # if new_module_name is None, it's entering class definition
        if not new_module_name:
            return

        curr_module_name = self.get_top_frame_module()
        if curr_module_name != new_module_name:
            logger.warning("Go into a different module")
            top_frame = self.top_frame_on_stack()
            top_frame.f_globals = dmf.share.analysis_modules[new_module_name].namespace

    def get_top_frame_module(self):
        top_frame: Frame = self.top_frame_on_stack()
        return top_frame.f_globals["__name__"]

    def get_top_fram_package(self):
        top_frame: Frame = self.top_frame_on_stack()
        return top_frame.f_globals["__package__"]

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


def union_state(state1: State, state2: State | STATE_BOT):
    if state2 == STATE_BOT:
        return state1

    state1 += state2
    return state1


def compute_value_of_expr(_, expr: ast.expr, state: State):
    if isinstance(expr, ast.Num):
        value = Value()
        if isinstance(expr.n, int):
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
        value.inject_str_type()
        return value
    elif isinstance(expr, ast.Bytes):
        value = Value()
        value.inject_bytes_type()
        return value
    elif isinstance(expr, ast.Compare):
        value = Value()
        value.inject_bool_type()
        return value
    elif isinstance(expr, ast.List):
        value = Value()
        list_type = ListType()
        value.inject_list_type(list_type)
        return value
    elif isinstance(expr, ast.Name):
        return state.read_var_from_stack(expr.id)
    elif isinstance(expr, ast.Attribute):
        receiver_value: Value = compute_value_of_expr(_, expr.value, state)
        receiver_attr: str = expr.attr
        value: Value = Value()

        def intercept(scope: str):
            if scope != "local":
                assert False

        for _, typ in receiver_value:
            if isinstance(typ, InsType):
                try:
                    v = analysis_heap.read_field_from_instance(typ, receiver_attr)
                except AttributeError:
                    pass
                else:
                    value += v
            elif isinstance(typ, FuncType):
                try:
                    attr_scope, attr_value = typ.getattr(receiver_attr)
                    intercept(attr_scope)
                except AttributeError:
                    pass
                else:
                    value += attr_value
            elif isinstance(typ, ClsType):
                try:
                    attr_scope, attr_value = typ.getattr(receiver_attr)
                    intercept(attr_scope)
                except AttributeError:
                    pass
                else:
                    value += attr_value
            elif isinstance(typ, ModuleType):
                try:
                    attr_scope, attr_value = typ.getattr(receiver_attr)
                    intercept(attr_scope)
                except AttributeError:
                    pass
                else:
                    value += attr_value
            else:
                logger.warn(typ)
        return value
    elif isinstance(expr, ast.BinOp):
        # left_value = compute_value_of_expr(expr.left, state)
        # right_value = compute_value_of_expr(expr.right, state)
        # left_prims = left_value.extract_prim_types()
        # right_prims = right_value.extract_prim_types()
        # value = Value()
        assert False
    else:
        assert False
