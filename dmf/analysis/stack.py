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
from collections import defaultdict
from typing import List

import dmf.share
from dmf.analysis.heap import analysis_heap
from dmf.analysis.value import (
    Value,
    Namespace,
    Var,
    InsType,
    FuncType,
    ClsType,
    ModuleType,
)
from dmf.log.logger import logger


class Frame:
    def __init__(self, f_locals=None, f_back=None, f_globals=None, f_builtins=None):
        self.f_locals: Namespace[Var, Value] = f_locals
        self.f_back: Frame | None = f_back
        self.f_globals: Namespace[Var, Value] = f_globals
        self.f_builtins: Namespace[Var, Value] = f_builtins

    # compare f_locals, f_globals and f_builtins
    # don't know how to compare f_back for now
    def __le__(self, other: Frame):
        res = self.f_locals <= other.f_locals and self.f_globals <= other.f_globals
        return res

    def __iadd__(self, other: Frame):
        self.f_locals += other.f_locals
        self.f_globals += other.f_globals
        return self

    def __repr__(self):
        return self.f_locals.__repr__()

    def read_special_var(self, var_name: str):
        return self.f_locals[var_name]

    def read_var(self, var_name: str, scope: str) -> Value:

        # Implement LEGB rule
        if var_name in self.f_locals:
            var_scope, var_value = self.f_locals.read_scope_and_value_by_name(var_name)
            if var_scope == "local":
                return var_value
            elif var_scope == "nonlocal":
                return self.read_nonlocal_frame(var_name)
            elif var_scope == "global":
                return self.read_global_frame(var_name)

        # use global keyword, then assign a value to the nonexistent var
        if scope == "global":
            return self.read_global_with_default(var_name)

        try:
            return self.read_nonlocal_frame(var_name)
        except AttributeError:
            pass

        try:
            return self.read_global_frame(var_name)
        except AttributeError:
            pass

        # try:
        #     return self.read_builtin_frame(var_name)
        # except AttributeError:
        #     pass

        raise AttributeError(var_name)

    # find one with (var_name, local)
    def read_nonlocal_frame(self, var_name: str) -> Value:
        parent_frame: Frame = self.f_back
        while (
            # not the last frame
            parent_frame is not None
            # share the same global namespace
            and parent_frame.f_globals is self.f_globals
            # parent_frame.f_locals itself should not be module namespace
            and parent_frame.f_locals is not self.f_globals
        ):
            if var_name in parent_frame.f_locals:
                (
                    var_scope,
                    var_value,
                ) = parent_frame.f_locals.read_scope_and_value_by_name(var_name)
                if var_scope != "local":
                    parent_frame = parent_frame.f_back
                else:
                    return var_value
            else:
                parent_frame = parent_frame.f_back
        raise AttributeError(var_name)

    def read_global_frame(self, var_name: str) -> Value:
        if var_name in self.f_globals:
            var_scope, var_value = self.f_globals.read_scope_and_value_by_name(var_name)
            if var_scope != "local":
                raise AttributeError(var_name)
            else:
                return var_value
        raise AttributeError(var_name)

    def read_builtin_frame(self, var_name: str) -> Value:
        if var_name in self.f_builtins:
            var_scope, var_value = self.f_builtins.read_scope_and_value_by_name(
                var_name
            )
            if var_scope != "local":
                raise AttributeError(var_name)
            else:
                return var_value
        raise AttributeError(var_name)

    def read_global_with_default(self, var_name: str):
        var: Var = Var(var_name, "local")
        return self.f_globals[var]

    def write_var(self, var_name: str, value: Value, scope: str):
        if var_name in self.f_locals:
            var_scope, pre_value = self.f_locals.read_scope_and_value_by_name(var_name)
            var: Var = Var(var_name, var_scope)
            if var_scope == "local":
                if self.f_locals is self.f_globals:
                    self.f_locals[var].inject_value(value)
                else:
                    self.f_locals[var] = value
            elif var_scope == "nonlocal":
                new_var = Var(var_name, "local")
                parent_frame: Frame = self.f_back
                while (
                    parent_frame is not None
                    and parent_frame.f_globals is self.f_globals
                ):
                    if var_name in parent_frame.f_locals:
                        (
                            var_scope,
                            _,
                        ) = parent_frame.f_locals.read_scope_and_value_by_name(var_name)
                        if var_scope != "local":
                            parent_frame = parent_frame.f_back
                        else:
                            parent_frame.f_locals[new_var] = value
                    else:
                        parent_frame = parent_frame.f_back
            elif var_scope == "global":
                new_var: Var = Var(var_name, "local")
                self.f_globals[new_var] = value
        else:
            var: Var = Var(var_name, scope)
            self.f_locals[var] = value

    def write_special_var(self, var_name: str, value):
        self.f_locals[var_name] = value


class Stack:
    def __init__(self, stack: Stack = None):
        # if self.frames is "BOT", it's BOT
        self.frames: List[Frame] | BOT = []
        if stack is not None:
            self.duplicate_frames(stack)

    def duplicate_frames(self, stack: Stack):
        memo = {}
        f_back: Frame | None = None
        for _, f in enumerate(stack.frames):

            frame = Frame()
            frame.f_back = f_back
            f_back = frame
            self.frames.append(frame)

            id_f_locals = id(f.f_locals)
            if id_f_locals not in memo:
                memo[id_f_locals] = f.f_locals.copy()
            frame.f_locals = memo[id_f_locals]

            id_f_globals = id(f.f_globals)
            if id_f_globals not in memo:
                memo[id_f_globals] = f.f_globals.copy()
            frame.f_globals = memo[id_f_globals]

        for name, module in dmf.share.analysis_modules.items():
            namespace = module.namespace
            id_namespace = id(namespace)
            if id_namespace in memo:
                module.namespace = memo[id_namespace]

    def __le__(self, other: Stack):
        if self.frames == BOT:
            return True
        if other.frames == BOT:
            return False

        frame_pairs = zip(reversed(self.frames), reversed(other.frames))
        for frame_pair in frame_pairs:
            if not frame_pair[0] <= frame_pair[1]:
                return False
        return True

    def __iadd__(self, other: Stack):
        if other.frames == BOT:
            return self

        frame_pairs = zip(reversed(self.frames), reversed(other.frames))
        for frame_pair1, frame_pair2 in frame_pairs:
            frame_pair1 += frame_pair2
        return self

    def __repr__(self):
        return self.frames.__repr__()

    def is_bot(self):
        return self.frames == BOT

    def push_frame(self, frame: Frame):
        self.frames.append(frame)

    def pop_frame(self) -> Frame:
        top = self.top_frame()
        self.frames = self.frames[:-1]
        return top

    def top_frame(self) -> Frame:
        return self.frames[-1]

    def top_frame_contains(self, name):
        return name in self.top_frame().f_locals

    def get_top_frame_module(self):
        return self.top_frame().f_globals["__name__"]

    def get_top_frame_package(self):
        return self.top_frame().f_globals["__package__"]

    def read_var(self, var: str, scope: str = "local"):
        return self.top_frame().read_var(var, scope)

    def read_special_var(self, var: str):
        return self.top_frame().read_special_var(var)

    def write_var(self, var: str, value: Value, scope: str = "local"):
        self.top_frame().write_var(var, value, scope)

    def write_special_var(self, var: str, value):
        self.top_frame().write_special_var(var, value)

    def copy(self):
        copied = Stack(self)
        return copied

    def next_ns(self):
        curr_frame = self.top_frame()

        new_f_locals = Namespace()
        new_f_back = curr_frame
        new_f_globals = curr_frame.f_globals
        new_f_builtins = curr_frame.f_builtins

        new_frame = Frame(
            f_locals=new_f_locals,
            f_back=new_f_back,
            f_globals=new_f_globals,
            f_builtins=new_f_builtins,
        )
        self.push_frame(new_frame)

    def check_module_diff(self, new_module_name=None):
        curr_module_name = self.get_top_frame_module()
        if curr_module_name != new_module_name:
            self.top_frame().f_globals = dmf.share.analysis_modules[
                new_module_name
            ].namespace

    def compute_value_of_expr(self, expr: ast.expr):
        value = Value()
        if isinstance(expr, ast.Num):
            if isinstance(expr.n, int):
                value.inject_int_type()
            else:
                assert False
            return value
        elif isinstance(expr, ast.NameConstant):
            if expr.value is None:
                value.inject_none_type()
            else:
                value.inject_bool_type()
            return value
        elif isinstance(expr, (ast.Str, ast.JoinedStr)):
            value.inject_str_type()
            return value
        elif isinstance(expr, ast.Bytes):
            value.inject_bytes_type()
            return value
        elif isinstance(expr, ast.Compare):
            value.inject_bool_type()
            return value
        elif isinstance(expr, ast.Name):
            old_value = self.read_var(expr.id)
            new_value = old_value.copy()
            return new_value
        elif isinstance(expr, ast.Attribute):
            receiver_value: Value = self.compute_value_of_expr(expr.value)
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
            logger.warn(expr)
            assert False


BOT = "BOT"


def stack_bot_builder() -> Stack:
    bot = Stack()
    bot.frames = BOT
    return bot
