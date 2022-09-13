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
    Int_Type,
)
from dmf.analysis.exceptions import ParsingDefaultsError, ParsingKwDefaultsError
from dmf.analysis.gets_sets import analysis_getattr
from dmf.analysis.heap import Heap
from dmf.analysis.implicit_names import POS_ARG_LEN, MODULE_NAME_FLAG
from dmf.analysis.stack import Stack, Frame
from dmf.analysis.value import Value, type_2_value


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
        init_module_name: str,
    ):
        self.stack: Stack = stack
        self.heap: Heap = heap
        self.init_first_stack_frame(init_module_name)

    def __repr__(self):
        return f"{self.stack}\n{self.heap}"

    def __le__(self, other):
        return self.stack <= other.stack and self.heap <= other.heap

    def __iadd__(self, other: State):
        self.stack += other.stack
        self.heap += other.heap
        return self

    def init_first_stack_frame(self, module_name: str):
        modules: Value = sys.analysis_modules[module_name]
        module = modules.extract_1_elt()
        global_ns = module.tp_dict
        self.stack.frames.append(
            Frame(f_locals=global_ns, f_back=None, f_globals=global_ns)
        )

    def switch_global_namespace(self, new_module_name):
        """
        if a function is called, its global namespace has to be switched.
        be careful in our setting moudle name -> Value
        :param new_module_name:
        :return:
        """
        module_value: Value = sys.analysis_modules[new_module_name]
        # one real module
        assert len(module_value) == 1, module_value
        real_module = module_value.value_2_list()[0]
        print("Switching", real_module.tp_dict)
        self.stack.frames[-1].f_globals = real_module.tp_dict

    def compute_value_of_expr(self, expr: ast.expr):
        if isinstance(
            expr,
            (
                ast.BoolOp,
                ast.BinOp,
                ast.UnaryOp,
                ast.Constant,
                ast.Subscript,
                ast.Starred,
                ast.Lambda,
                ast.IfExp,
                ast.Dict,
                ast.Set,
                ast.ListComp,
                ast.SetComp,
                ast.GeneratorExp,
                ast.Await,
                ast.Call,
                ast.List,
                ast.Tuple,
            ),
        ):
            raise NotImplementedError(expr)
        elif isinstance(expr, ast.Attribute):
            value = Value()
            receiver_value = self.compute_value_of_expr(expr.value)
            for one_receiver in receiver_value:
                one_value = analysis_getattr(one_receiver, expr.attr)
                value.inject_value(one_value)
            return value
        elif isinstance(expr, ast.Yield):
            return self.compute_value_of_expr(expr.value)
        elif isinstance(expr, ast.YieldFrom):
            return Value.make_any()
        elif isinstance(expr, ast.Compare):
            value = type_2_value(Bool_Instance)
            return value
        elif isinstance(expr, ast.Num):
            if isinstance(expr.n, int):
                value = type_2_value(Int_Type())
                return value
            elif isinstance(expr.n, float):
                value = type_2_value(Float_Instance)
                return value
            elif isinstance(expr.n, complex):
                raise NotImplementedError(expr)
        elif isinstance(expr, (ast.Str, ast.JoinedStr, ast.FormattedValue)):
            value = type_2_value(Str_Instance)
            return value
        elif isinstance(expr, ast.Bytes):
            value = type_2_value(Bytes_Instance)
            return value
        elif isinstance(expr, ast.NameConstant):
            if expr.value is None:
                value = type_2_value(None_Instance)
                return value
            else:
                value = type_2_value(Bool_Instance)
                return value
        elif isinstance(expr, ast.Ellipsis):
            value = type_2_value(Ellipsis_Instance)
            return value
        elif isinstance(expr, ast.Name):
            value = self.stack.read_var(expr.id)
            return value
        elif isinstance(expr, ast.Index):
            value = self.compute_value_of_expr(expr.value)
            return value
        else:
            raise NotImplementedError(expr)

    def compute_function_defaults(self, node: ast.FunctionDef):
        arguments: ast.arguments = node.args

        # defaults is a list of default values for arguments that can be passed positionally.
        # If there are fewer defaults, they correspond to the last n arguments.
        args_diff_len = len(arguments.args) - len(arguments.defaults)
        defaults = [None] * args_diff_len
        for default in arguments.defaults:
            default_value = self.compute_value_of_expr(default)
            defaults.append(default_value)

        # kw_defaults is a list of default values for keyword-only arguments.
        # If one is None, the corresponding argument is required.
        kwdefaults = []
        for kw_default in arguments.kw_defaults:
            if kw_default is None:
                kwdefaults.append(kw_default)
            else:
                kw_default_value = self.compute_value_of_expr(kw_default)
                kwdefaults.append(kw_default_value)

        return defaults, kwdefaults

    def compute_func_args(self, args: List[ast.expr], keywords: List[ast.keyword]):
        computed_args = []
        for arg in args:
            val = self.compute_value_of_expr(arg)
            computed_args.append(val)

        computed_keywords = {}
        for keyword in keywords:
            val = self.compute_value_of_expr(keyword.value)
            computed_keywords[keyword.arg] = val
        return computed_args, computed_keywords

    def compute_bases(self, node: ast.ClassDef) -> List[List]:
        # should I use state at call label or state at return label?
        base_types: List[List] = []
        if node.bases:
            for base in node.bases:
                cls_types = self.compute_value_of_expr(base)
                cls_type_list = cls_types.value_2_list()
                base_types.append(cls_type_list)
        else:
            base_types.append([Object_Type])
        return base_types

    def parse_positional_args(self, start_pos: int, arguments: ast.arguments):
        args_flag = [False for _ in arguments.args]
        stack = self.stack
        f_locals = stack.top_frame().f_locals
        positional_len: int = getattr(f_locals, POS_ARG_LEN)
        real_pos_len = positional_len - start_pos + 1

        if real_pos_len > len(arguments.args):
            if arguments.vararg is None:
                raise TypeError(arguments.vararg)

            for idx, arg in enumerate(arguments.args):
                arg_value = f_locals.read_value(str(idx))
                stack.write_var(arg.arg, "local", arg_value)
                args_flag[idx] = True
                f_locals.del_local_var(str(idx))

            # idx += 1
            # # consider vararg
            # while idx < real_pos_len:
            #     f_locals.del_local_var(str(idx))
            #     idx += 1

        else:
            for arg_idx, pos_idx in enumerate(range(start_pos, positional_len + 1)):
                arg = arguments.args[arg_idx]
                arg_value = f_locals.read_value(str(pos_idx))
                stack.write_var(arg.arg, "local", arg_value)
                args_flag[arg_idx] = True
                f_locals.del_local_var(str(pos_idx))

        if arguments.vararg:
            f_locals.write_local_value(arguments.vararg.arg, Value.make_any())

        return args_flag

    def parse_keyword_args(self, arg_flags, arguments: ast.arguments):
        stack = self.stack
        f_locals = stack.top_frame().f_locals

        # keyword arguments
        for idx, elt in enumerate(arg_flags):
            arg_name = arguments.args[idx].arg
            if not elt:
                if arg_name in f_locals:
                    arg_flags[idx] = True
        return arg_flags

    def parse_default_args(
        self, arg_flags: List, arguments: ast.arguments, defaults: List
    ):
        stack = self.stack
        for idx, elt in enumerate(arg_flags):
            if not elt:
                arg_name = arguments.args[idx].arg
                default = defaults[idx]
                if default is None:
                    raise ParsingDefaultsError
                stack.write_var(arg_name, "local", default)
                arg_flags[idx] = True
        assert all(arg_flags), arg_flags
        return arg_flags

    def parse_kwonly_args(self, arguments: ast.arguments, kwdefaults: Dict):
        stack = self.stack
        f_locals = stack.top_frame().f_locals
        for idx, kwonly_arg in enumerate(arguments.kwonlyargs):
            kwonly_arg_name = kwonly_arg.arg
            if kwonly_arg_name not in f_locals:
                default_value = kwdefaults[idx]
                # if default_value is None, no default value for this kw only
                if default_value is None:
                    raise ParsingKwDefaultsError
                else:
                    stack.write_var(kwonly_arg_name, "local", default_value)
        # TODO: kwargs
        if arguments.kwarg:
            stack.write_var(arguments.kwarg.arg, "local", Value.make_any())


def deepcopy_state(state: State, program_point) -> State:

    # main_modules = sys.analysis_modules["__main__"]
    # main_module = main_modules.value_2_list()[0]
    # main_globals = main_module.tp_dict
    # curr_state = state
    # curr_globals = curr_state.stack.frames[-1].f_globals

    memo = {}
    # sys.analysis_modules = deepcopy(sys.analysis_modules, memo)
    new_state = deepcopy(state, memo)

    # one bug here is if using import xxx, current module namespace will be updated
    # but it lost track of sys.modules
    # for example, import x. doing transfer on module x
    # then go back. prev f_globals
    for frame in new_state.stack.frames:
        f_globals = frame.f_globals
        module_name = getattr(f_globals, MODULE_NAME_FLAG)
        module_values = sys.analysis_modules[module_name]
        for module in module_values:
            module.tp_dict = f_globals

    # main_modules = sys.analysis_modules["__main__"]
    # main_module = main_modules.value_2_list()[0]
    # main_globals = main_module.tp_dict
    #
    # curr_state = new_state
    # curr_globals = curr_state.stack.frames[-1].f_globals

    # print(main_globals is curr_globals)

    sys.stack = new_state.stack
    sys.heap = new_state.heap
    sys.program_point = program_point
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
