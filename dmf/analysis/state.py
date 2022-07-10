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
from copy import deepcopy
from typing import Tuple, List

import dmf.share
from dmf.analysis.namespace import Heap, my_object
from dmf.analysis.stack import Stack
from dmf.analysis.variables import POS_ARG_END, Namespace_Local

State = Tuple[Stack, Heap]

BOTTOM = object()


def deepcopy_state(state: State) -> State:
    stack, heap = state
    memo = {}
    new_heap = deepcopy(heap, memo)
    new_stack = deepcopy(stack, memo)
    for name, module in dmf.share.analysis_modules.items():
        module.namespace = deepcopy(module.namespace, memo)
    return new_stack, new_heap


def is_bot_state(state: State) -> bool:
    if state is BOTTOM:
        return True
    return False


def compare_states(lhs: State | BOTTOM, rhs: State | BOTTOM) -> bool:
    if is_bot_state(lhs):
        return True
    if is_bot_state(rhs):
        return False

    res = lhs[0] <= rhs[0] and lhs[1] <= rhs[1]
    return res


def merge_states(lhs: State, rhs: State | BOTTOM) -> State:
    # if lhs is BOTTOM, we won't get here.
    if is_bot_state(rhs):
        return lhs

    lhs[0] += rhs[0]
    lhs[1] += rhs[1]
    return lhs


def compute_function_defaults(state: State, node: ast.FunctionDef):
    stack, heap = state

    # https: // docs.python.org / 3.11 / library / ast.html  # ast.arguments
    args: ast.arguments = node.args

    # defaults is a list of default values for arguments that can be passed positionally.
    # If there are fewer defaults, they correspond to the last n arguments.
    args_diff_len = len(args.args) - len(args.defaults)
    args.nl_defaults = []
    for default in args.defaults:
        default_value = stack.compute_value_of_expr(default)
        args.nl_defaults.append(default_value)
    args.nl_defaults = [None] * args_diff_len + args.nl_defaults

    # kw_defaults is a list of default values for keyword-only arguments.
    # If one is None, the corresponding argument is required.
    args.nl_kw_defaults = []
    for kw_default in args.kw_defaults:
        if kw_default is None:
            args.nl_kw_defaults.append(kw_default)
        else:
            kw_default_value = stack.compute_value_of_expr(kw_default)
            args.nl_kw_defaults.append(kw_default_value)


def compute_bases(state: State, node: ast.ClassDef):
    # should I use state at call label or state at return label?
    stack, heap = state
    if node.bases:
        base_types = []
        for base in node.bases:
            cls_types = stack.compute_value_of_expr(base)
            assert len(cls_types) == 1
            for cls in cls_types:
                base_types.append(cls)
        return base_types
    else:
        default_base = my_object
        return [default_base]


def parse_positional_args(start_pos: int, arguments: ast.arguments, state: State):
    args_flag = [False for _ in arguments.args]
    stack = state[0]
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
            f_locals.del_local_var(str(arg_idx))
    return args_flag


def parse_keyword_args(arg_flags, arguments: ast.arguments, state: State):
    stack = state[0]
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
    assert all(arg_flags)
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
        val = stack.compute_value_of_expr(arg)
        computed_args.append(val)

    computed_keywords = {}
    for keyword in keywords:
        val = stack.compute_value_of_expr(keyword.value)
        computed_keywords[keyword.arg] = val
    return computed_args, computed_keywords
