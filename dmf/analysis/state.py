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
from typing import List

from dmf.analysis._type_operations import AnalysisClass, _getattr, AnalysisInstance
from dmf.analysis.analysis_types import (
    POS_ARG_END,
    Namespace_Local,
    Object_Type,
    Int_Instance,
    Float_Instance,
    Complex_Instance,
    None_Instance,
    Bool_Instance,
    Str_Instance,
    Bytes_Instance,
)
from dmf.analysis.heap import Heap
from dmf.analysis.stack import Stack
from dmf.analysis.value import Value
from dmf.log.logger import logger


class StateBottom:
    pass


BOTTOM = StateBottom()


class State:
    def __init__(self, stack: Stack, heap: Heap):
        self.stack: Stack = stack
        self.heap: Heap = heap

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
                value.inject_type(Int_Instance)
            elif isinstance(expr.n, float):
                value.inject_type(Float_Instance)
            elif isinstance(expr.n, complex):
                value.inject_type(Complex_Instance)
            return value
        elif isinstance(expr, ast.NameConstant):
            if expr.value is None:
                value.inject_type(None_Instance)
            else:
                value.inject_type(Bool_Instance)
        elif isinstance(expr, (ast.Str, ast.JoinedStr)):
            value.inject_type(Str_Instance)
        elif isinstance(expr, ast.Bytes):
            value.inject_type(Bytes_Instance)
        elif isinstance(expr, ast.Compare):
            value.inject_type(Bool_Instance)
        elif isinstance(expr, ast.Name):
            value = self.stack.read_var(expr.id)
        elif isinstance(expr, ast.Attribute):
            receiver_value: Value = self.compute_value_of_expr(expr.value)
            receiver_attr: str = expr.attr
            value: Value = Value()
            for type in receiver_value:
                if isinstance(type, AnalysisClass):
                    res, descrs = _getattr(type, receiver_attr)
                    value.inject_value(res)
                elif isinstance(type, AnalysisInstance):
                    res, descrs = _getattr(type, receiver_attr)
                    value.inject_value(res)
                # elif isinstance(type, FunctionObject):
                #     try:
                #         tmp = Getattr(type, receiver_attr)
                #     except AttributeError:
                #         pass
                #     else:
                #         value.inject_value(tmp)
            return value
        elif isinstance(expr, ast.BinOp):
            raise NotImplementedError(expr)
        else:
            logger.warn(expr)
            assert False, expr
        return value


def deepcopy_state(state: State) -> State:
    memo = {}
    if "imported" in sys.analysis_modules:
        print(
            id(state.stack.frames[0].f_locals),
            id(sys.analysis_modules["imported"].tp_dict),
        )
    new_state = deepcopy(state, memo)
    sys.analysis_modules = deepcopy(sys.analysis_modules, memo)
    if "imported" in sys.analysis_modules:
        print(
            id(new_state.stack.frames[0].f_locals),
            id(sys.analysis_modules["imported"].tp_dict),
        )
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
        default_value = stack.compute_value_of_expr(default)
        defaults.append(default_value)

    # kw_defaults is a list of default values for keyword-only arguments.
    # If one is None, the corresponding argument is required.
    kwdefaults = []
    for kw_default in arguments.kw_defaults:
        if kw_default is None:
            kwdefaults.append(kw_default)
        else:
            kw_default_value = stack.compute_value_of_expr(kw_default)
            kwdefaults.append(kw_default_value)

    if arguments.vararg:
        raise NotImplementedError
    if arguments.kwarg:
        raise NotImplementedError

    return defaults, kwdefaults


def compute_bases(state: State, node: ast.ClassDef):
    # should I use state at call label or state at return label?
    stack, heap = state.stack, state.heap
    if node.bases:
        base_types = []
        for base in node.bases:
            cls_types = state.compute_value_of_expr(base)
            assert len(cls_types) == 1
            for cls in cls_types:
                base_types.append(cls)
        return base_types
    else:
        default_base = Object_Type
        return [default_base]


def parse_positional_args(start_pos: int, arguments: ast.arguments, state: State):
    args_flag = [False for _ in arguments.args]
    stack = state.stack
    f_locals = stack.top_frame().f_locals
    positional_len: int = f_locals.read_value(POS_ARG_END)
    real_pos_len = positional_len - start_pos + 1

    if real_pos_len > len(arguments.args):
        if arguments.vararg is None:
            raise TypeError

        for idx, arg in enumerate(arguments.args):
            arg_value = f_locals.read_value(str(idx))
            stack.write_var(arg.arg, Namespace_Local, arg_value)
            args_flag[idx] = True
            f_locals.del_local_var(str(idx))
        # TODO: vararg
        if arguments.vararg is not None:
            raise NotImplementedError
    else:
        for arg_idx, pos_idx in enumerate(range(start_pos, positional_len + 1)):
            arg = arguments.args[arg_idx]
            arg_value = f_locals.read_value(str(pos_idx))
            stack.write_var(arg.arg, Namespace_Local, arg_value)
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


def parse_default_args(arg_flags, arguments: ast.arguments, state: State):
    stack = state[0]
    for idx, elt in enumerate(arg_flags):
        if not elt:
            arg_name = arguments.args[idx].arg
            default = arguments.nl_defaults[idx]
            if default is None:
                raise TypeError
            stack.write_var(arg_name, Namespace_Local, default)
            arg_flags[idx] = True
    assert all(arg_flags), arg_flags
    return arg_flags


def parse_kwonly_args(arguments: ast.arguments, state: State):
    stack = state[0]
    f_locals = stack.top_frame().f_locals
    for idx, kwonly_arg in enumerate(arguments.kwonlyargs):
        kwonly_arg_name = kwonly_arg.arg
        if kwonly_arg_name not in f_locals:
            default_value = arguments.nl_kw_defaults[idx]
            if default_value is None:
                raise TypeError
            else:
                stack.write_var(kwonly_arg_name, Namespace_Local, default_value)
    # TODO: kwargs
    if arguments.kwarg is not None:
        raise NotImplementedError


def compute_func_args(state: State, args: List[ast.expr], keywords: List[ast.keyword]):
    stack, heap = state

    computed_args = []
    for arg in args:
        val = state.compute_value_of_expr(arg)
        computed_args.append(val)

    computed_keywords = {}
    for keyword in keywords:
        val = state.compute_value_of_expr(keyword.value)
        computed_keywords[keyword.arg] = val
    return computed_args, computed_keywords
