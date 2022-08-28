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
import sys
from copy import deepcopy
from typing import List, Dict

from dmf.analysis.analysis_types import (
    Float_Instance,
    Str_Instance,
    Bool_Instance,
    Bytes_Instance,
    None_Instance,
    Ellipsis_Instance,
    Object_Type,
    Int_Instance,
)
from dmf.analysis.gets_sets import getattrs
from dmf.analysis.heap import Heap
from dmf.analysis.implicit_names import POS_ARG_LEN
from dmf.analysis.stack import Stack
from dmf.analysis.value import Value, type_2_value
from dmf.log.logger import logger


class StateBottom:
    def __repr__(self):
        return "Bottom"

    def __deepcopy__(self, memo):
        if id(self) not in memo:
            memo[id(self)] = self
        return memo[id(self)]


BOTTOM = StateBottom()


class State:
    def __init__(
        self,
        stack: Stack,
        heap: Heap,
        analysis_modules: Dict,
        fake_analysis_modules: Dict,
    ):
        self.stack: Stack = stack
        self.heap: Heap = heap
        self.analysis_modules: Dict = analysis_modules
        self.fake_analysis_modules: Dict = fake_analysis_modules

    def __repr__(self):
        return repr(self.stack)

    def __iadd__(self, other: State):
        self.stack += other.stack
        self.heap += other.heap
        return self

    def compute_value_of_expr(self, expr: ast.expr):
        value = Value()
        if isinstance(expr, ast.Num):
            if isinstance(expr.n, int):
                value = type_2_value(Int_Instance)
                return value
            elif isinstance(expr.n, float):
                value = type_2_value(Float_Instance)
                return value
            elif isinstance(expr.n, complex):
                raise NotImplementedError(expr)
        elif isinstance(expr, ast.NameConstant):
            if expr.value is None:
                value.inject_type(None_Instance)
            else:
                value = type_2_value(Bool_Instance)
                return value
        elif isinstance(expr, (ast.Str, ast.JoinedStr)):
            value = type_2_value(Str_Instance)
            return value
        elif isinstance(expr, ast.Bytes):
            value = type_2_value(Bytes_Instance)
            return value
        elif isinstance(expr, ast.Compare):
            value = type_2_value(Bool_Instance)
            return value
        elif isinstance(expr, ast.Name):
            value = self.stack.read_var(expr.id)
            return value
        elif isinstance(expr, ast.Attribute):
            receiver_value: Value = self.compute_value_of_expr(expr.value)
            value = getattrs(receiver_value, expr.attr)
            return value
        elif isinstance(expr, ast.BinOp):
            raise NotImplementedError(expr)
        elif isinstance(expr, ast.Constant):
            raise NotImplementedError(expr)
        elif isinstance(expr, ast.Ellipsis):
            value = type_2_value(Ellipsis_Instance)
            return value
        else:
            logger.warn(expr)
            raise NotImplementedError(expr)


def deepcopy_state(state: State) -> State:
    memo = {}
    new_state = deepcopy(state, memo)
    sys.stack = new_state.stack
    sys.heap = new_state.heap
    sys.analysis_modules = new_state.analysis_modules
    sys.fake_analysis_modules = new_state.fake_analysis_modules
    return new_state


def is_bot_state(state: State) -> bool:
    if state is BOTTOM:
        return True
    return False


def compare_states(lhs: State | BOTTOM, rhs: State | BOTTOM) -> bool:
    if is_bot_state(lhs):
        return True
    if is_bot_state(rhs):
        return False

    res = lhs.stack <= rhs.stack and lhs.heap <= rhs.heap
    return res


def merge_states(lhs: State, rhs: State | BOTTOM) -> State:
    # if lhs is BOTTOM, we won't get here.
    if is_bot_state(rhs):
        return lhs

    lhs += rhs
    return lhs


def compute_function_defaults(state: State, node: ast.FunctionDef):
    stack, _ = state.stack, state.heap

    # https: // docs.python.org / 3.11 / library / ast.html  # ast.arguments
    arguments: ast.arguments = node.args

    # defaults is a list of default values for arguments that can be passed positionally.
    # If there are fewer defaults, they correspond to the last n arguments.
    args_diff_len = len(arguments.args) - len(arguments.defaults)
    defaults = [None] * args_diff_len
    for default in arguments.defaults:
        default_value = state.compute_value_of_expr(default)
        defaults.append(default_value)

    # kw_defaults is a list of default values for keyword-only arguments.
    # If one is None, the corresponding argument is required.
    kwdefaults = []
    for kw_default in arguments.kw_defaults:
        if kw_default is None:
            kwdefaults.append(kw_default)
        else:
            kw_default_value = state.compute_value_of_expr(kw_default)
            kwdefaults.append(kw_default_value)

    if arguments.vararg:
        raise NotImplementedError
    if arguments.kwarg:
        raise NotImplementedError

    return defaults, kwdefaults


def compute_bases(state: State, node: ast.ClassDef):
    # should I use state at call label or state at return label?
    if node.bases:
        base_types = []
        for base in node.bases:
            cls_types = state.compute_value_of_expr(base)
            assert len(cls_types) == 1
            for cls in cls_types:
                base_types.append(cls)
        return base_types
    else:
        default_base = [Object_Type]
        return [default_base]


def parse_positional_args(start_pos: int, arguments: ast.arguments, state: State):
    args_flag = [False for _ in arguments.args]
    stack = state.stack
    f_locals = stack.top_frame().f_locals
    # positional_len: int = f_locals.read_value(POS_ARG_END)
    positional_len: int = getattr(f_locals, POS_ARG_LEN)
    real_pos_len = positional_len - start_pos + 1

    if real_pos_len > len(arguments.args):
        if arguments.vararg is None:
            raise TypeError

        for idx, arg in enumerate(arguments.args):
            arg_value = f_locals.read_value(str(idx))
            stack.write_var(arg.arg, "local", arg_value)
            args_flag[idx] = True
            f_locals.del_local_var(str(idx))
        # TODO: vararg
        if arguments.vararg is not None:
            raise NotImplementedError
    else:
        for arg_idx, pos_idx in enumerate(range(start_pos, positional_len + 1)):
            arg = arguments.args[arg_idx]
            arg_value = f_locals.read_value(str(pos_idx))
            stack.write_var(arg.arg, "local", arg_value)
            args_flag[arg_idx] = True
            f_locals.del_local_var(str(pos_idx))
    return args_flag


def parse_keyword_args(arg_flags, arguments: ast.arguments, state: State):
    stack = state.stack
    f_locals = stack.top_frame().f_locals

    # keyword arguments
    for idx, elt in enumerate(arg_flags):
        arg_name = arguments.args[idx].arg
        if not elt:
            if arg_name in f_locals:
                arg_flags[idx] = True
    return arg_flags


def parse_default_args(arg_flags, arguments: ast.arguments, state: State, defaults):
    stack = state.stack
    for idx, elt in enumerate(arg_flags):
        if not elt:
            arg_name = arguments.args[idx].arg
            default = defaults[idx]
            if default is None:
                raise TypeError
            stack.write_var(arg_name, "local", default)
            arg_flags[idx] = True
    assert all(arg_flags), arg_flags
    return arg_flags


def parse_kwonly_args(arguments: ast.arguments, state: State, kwdefaults):
    stack = state.stack
    f_locals = stack.top_frame().f_locals
    for idx, kwonly_arg in enumerate(arguments.kwonlyargs):
        kwonly_arg_name = kwonly_arg.arg
        if kwonly_arg_name not in f_locals:
            default_value = kwdefaults[idx]
            if default_value is None:
                raise TypeError
            else:
                stack.write_var(kwonly_arg_name, "local", default_value)
    # TODO: kwargs
    if arguments.kwarg is not None:
        raise NotImplementedError


def compute_func_args(state: State, args: List[ast.expr], keywords: List[ast.keyword]):

    computed_args = []
    for arg in args:
        val = state.compute_value_of_expr(arg)
        computed_args.append(val)

    computed_keywords = {}
    for keyword in keywords:
        val = state.compute_value_of_expr(keyword.value)
        computed_keywords[keyword.arg] = val
    return computed_args, computed_keywords
