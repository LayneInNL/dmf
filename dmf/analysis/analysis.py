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
from collections import defaultdict, deque
from copy import deepcopy
from typing import Dict, Tuple, Deque, Set, List

import dmf.share
from dmf.analysis.namespace import (
    ModuleType,
    analysis_heap,
    CustomClass,
    FunctionObject,
    my_object,
    MethodObject,
    dunder_lookup,
    Constructor,
    my_setattr,
    Namespace,
    mock_value,
    SpecialMethodObject,
    my_getattr,
    DescriptorGetMethod,
    DescriptorSetMethod,
    BuiltinList,
    BuiltinTuple,
)
from dmf.analysis.prim import NoneType
from dmf.analysis.stack import Frame, Stack, stack_bot_builder
from dmf.analysis.value import Value, create_value_with_type
from dmf.analysis.variables import (
    Namespace_Local,
    Namespace_Nonlocal,
    Namespace_Global,
    RETURN_FLAG,
    POSITION_FLAG,
    INIT_FLAG,
    Namespace_Helper,
)
from dmf.flows import CFG
from dmf.flows.flows import BasicBlock
from dmf.flows.temp import Unused_Name
from dmf.log.logger import logger

Empty_Ctx = ()
Ctx = Tuple
Heap = int
Lab = int
Basic_Flow = Tuple[Lab, Lab]
ProgramPoint = Tuple[int, Ctx]
Flow = Tuple[ProgramPoint, ProgramPoint]
Inter_Flow = Tuple[ProgramPoint, ProgramPoint, ProgramPoint, ProgramPoint]


def record(label: Lab, context: Ctx):
    return label


def merge(label: Lab, heap, context: Ctx):
    return context[-1:] + (label,)


class Base:
    def __init__(self):
        self.flows: Set[Basic_Flow] = dmf.share.flows

        self.dummy_labels = dmf.share.dummy_labels
        self.call_labels = dmf.share.call_labels
        self.return_labels = dmf.share.return_labels
        self.call_return_inter_flows = dmf.share.call_return_inter_flows
        self.classdef_inter_flows = dmf.share.classdef_inter_flows
        self.setter_inter_flows = dmf.share.setter_inter_flows
        self.getter_inter_flows = dmf.share.getter_inter_flows
        self.special_init_flows = dmf.share.special_init_inter_flows

        self.blocks: Dict[Lab, BasicBlock] = dmf.share.blocks
        self.sub_cfgs: Dict[Lab, CFG] = dmf.share.sub_cfgs
        self.inter_flows: Set[Inter_Flow] = set()

    def get_stmt_by_label(self, label: int):
        return self.blocks[label].stmt[0]

    def get_stmt_by_point(self, program_point: ProgramPoint):
        label, _ = program_point
        return self.get_stmt_by_label(label)

    def is_dummy_label(self, label: int):
        return label in self.dummy_labels

    def is_dummy_point(self, program_point: ProgramPoint):
        label, _ = program_point
        return self.is_dummy_label(label)

    def is_call_label(self, label: int):
        return label in self.call_labels

    def is_call_point(self, program_point: ProgramPoint):
        label, _ = program_point
        return self.is_call_label(label)

    def is_return_label(self, label: int):
        return label in self.return_labels

    def is_return_point(self, program_point: ProgramPoint):
        label, _ = program_point
        return self.is_return_label(label)

    def is_normal_call_label(self, label):
        for l1, *_ in self.call_return_inter_flows:
            if label == l1:
                return True
        return False

    def is_normal_call_point(self, program_point: ProgramPoint):
        label, _ = program_point
        return self.is_normal_call_label(label)

    def is_special_init_call_label(self, label: int):
        for call, *_ in self.special_init_flows:
            if label == call:
                return True
        return False

    def is_special_init_call_point(self, program_point: ProgramPoint):
        label, _ = program_point
        return self.is_special_init_call_label(label)

    def is_getter_call_label(self, label):
        for call, *_ in self.getter_inter_flows:
            if label == call:
                return True
        return False

    def is_getter_call_point(self, program_point: ProgramPoint):
        label, _ = program_point
        return self.is_getter_call_label(label)

    def is_setter_call_label(self, label):
        for call, *_ in self.setter_inter_flows:
            if label == call:
                return True
        return False

    def is_setter_call_point(self, program_point: ProgramPoint):
        label, _ = program_point
        return self.is_setter_call_label(label)

    def is_classdef_call_label(self, label: int):
        for (
            call,
            *_,
        ) in self.classdef_inter_flows:
            if label == call:
                return True
        return False

    def is_classdef_call_point(self, program_point: ProgramPoint):
        label, _ = program_point
        return self.is_classdef_call_label(label)

    def is_entry_point(self, program_point: ProgramPoint):
        for _, entry_point, _, _ in self.inter_flows:
            if program_point == entry_point:
                return True
        return False

    def is_exit_point(self, program_point: ProgramPoint):
        for _, _, exit_point, _ in self.inter_flows:
            if program_point == exit_point:
                return True
        return False

    def get_classdef_call_label(self, label):
        for call_label, return_label in self.classdef_inter_flows:
            if label == return_label:
                return call_label
        raise KeyError

    def get_classdef_return_label(self, label):
        for call_label, return_label in self.classdef_inter_flows:
            if label == call_label:
                return return_label
        raise KeyError

    def get_getter_return_label(self, label):
        for call_label, return_label, dummy_return_label in self.getter_inter_flows:
            if label == call_label:
                return return_label, dummy_return_label
        raise KeyError

    def get_setter_return_label(self, label):
        for call_label, return_label, dummy_return_label in self.setter_inter_flows:
            if label == call_label:
                return return_label, dummy_return_label
        raise KeyError

    def get_new_return_label(self, label):
        for l1, l2, l3, l4, l5, l6, l7 in self.call_return_inter_flows:
            if label == l1:
                return l2, l3
        raise KeyError

    def get_func_return_label(self, label):
        for l1, l2, l3, l4, l5, l6, l7 in self.call_return_inter_flows:
            if label == l1:
                return l6, l7
        raise KeyError

    def get_init_return_label(self, label):
        for l1, l2, l3 in self.special_init_flows:
            if label == l1:
                return l2, l3
        raise KeyError

    def add_sub_cfg(self, cfg: CFG):
        dmf.share.update_global_info(cfg)

    def DELTA(self, program_point: ProgramPoint):
        added = []
        added += self.DELTA_basic_flow(program_point)
        added += self.DELTA_call_flow(program_point)
        added += self.DELTA_exit_flow(program_point)
        return added

    def DELTA_basic_flow(self, program_point: ProgramPoint):
        added = []
        label, context = program_point
        for fst_lab, snd_lab in self.flows:
            if label == fst_lab:
                added.append(((label, context), (snd_lab, context)))
        return added

    def DELTA_call_flow(self, program_point: ProgramPoint):
        added = []
        for (
            call_point,
            entry_point,
            exit_point,
            return_point,
        ) in self.inter_flows:
            if program_point == call_point:
                added.append((call_point, entry_point))
                added.append((exit_point, return_point))
        return added

    def DELTA_exit_flow(self, program_point):
        added = []
        for (
            _,
            _,
            exit_point,
            return_point,
        ) in self.inter_flows:
            if program_point == exit_point:
                added.append((exit_point, return_point))
        return added


class Analysis(Base):
    def __init__(self, module_name):
        super().__init__()
        self.entry_info: Dict = {}
        self.getter_info: Dict = {}
        self.setter_info: Dict = {}
        self.work_list: Deque[Flow] = deque()
        self.analyzed_program_points = None
        self.extremal_value: Stack = Stack()

        curr_module: ModuleType = dmf.share.analysis_modules[module_name]
        start_lab, final_lab = curr_module.entry_label, curr_module.exit_label
        self.extremal_point: ProgramPoint = (start_lab, Empty_Ctx)
        self.final_point: ProgramPoint = (final_lab, Empty_Ctx)

        # init first frame
        def init_first_frame(extremal_value, module):
            global_ns = module.namespace
            extremal_value.push_frame(
                Frame(
                    f_locals=global_ns,
                    f_back=None,
                    f_globals=global_ns,
                )
            )

        init_first_frame(self.extremal_value, curr_module)

    def compute_fixed_point(self):
        self.initialize()
        self.iterate()
        self.present()

    def initialize(self):
        # add flows to work_list
        self.work_list.extendleft(self.DELTA(self.extremal_point))
        # default init analysis_list
        self.analysis_list: defaultdict[ProgramPoint, Stack] = defaultdict(
            stack_bot_builder
        )
        self.analysis_effect_list = {}
        # update extremal label
        self.analysis_list[self.extremal_point] = self.extremal_value
        self.analyzed_program_points = {self.extremal_point}

    def iterate(self):
        while self.work_list:
            program_point1, program_point2 = self.work_list.popleft()
            logger.debug(
                "Current program point1 {} and lattice1 {}".format(
                    program_point1, self.analysis_list[program_point1]
                )
            )

            transferred: Stack = self.transfer(program_point1)
            old: Stack = self.analysis_list[program_point2]

            if not transferred <= old:
                transferred += old
                self.analysis_list[program_point2]: Stack = transferred
                self.LAMBDA(program_point2)
                added_program_points = self.DELTA(program_point2)
                if not added_program_points:
                    logger.critical("No added flows at {}".format(program_point2))
                else:
                    logger.debug("added flows {}".format(added_program_points))
                    self.analyzed_program_points.add(program_point2)
                    self.work_list.extendleft(added_program_points)
            logger.debug(
                "Current program point2 {} and lattice2 {}".format(
                    program_point2, self.analysis_list[program_point2]
                )
            )

    def present(self):
        self.analyzed_program_points.add(self.final_point)
        for program_point in self.analyzed_program_points:
            logger.info(
                "Context at program point {}: {}".format(
                    program_point, self.analysis_list[program_point]
                )
            )
            self.analysis_effect_list[program_point] = self.transfer(program_point)
            logger.info(
                "Effect at program point {}: {}".format(
                    program_point, self.analysis_effect_list[program_point]
                )
            )
        self.transfer(self.final_point)
        print(analysis_heap)
        # logger.warning(dmf.share.analysis_modules["static_builtins"].namespace)

    def compute_func_args(
        self, stack: Stack, args: List[ast.expr], keywords: List[ast.keyword]
    ):
        computed_args = []
        for arg in args:
            val = stack.compute_value_of_expr(arg)
            computed_args.append(val)

        computed_keywords = {}
        for keyword in keywords:
            val = stack.compute_value_of_expr(keyword.value)
            computed_keywords[keyword.arg] = val
        return computed_args, computed_keywords

    # based on current program point, update self.IF
    def LAMBDA(self, program_point: ProgramPoint) -> None:
        old_stack: Stack = self.analysis_list[program_point]
        new_stack: Stack = deepcopy(old_stack)
        # we are only interested in call labels
        if self.is_call_point(program_point):
            if self.is_classdef_call_point(program_point):
                self._lambda_classdef(program_point, old_stack, new_stack)
            elif self.is_normal_call_point(program_point):
                self._lambda_normal(program_point, old_stack, new_stack)
            elif self.is_special_init_call_point(program_point):
                self._lambda_special_init(program_point, old_stack, new_stack)
            elif self.is_getter_call_point(program_point):
                self._lambda_getter(program_point, old_stack, new_stack)
            elif self.is_setter_call_point(program_point):
                self._lambda_setter(program_point, old_stack, new_stack)

    def _lambda_constructor(
        self,
        program_point: ProgramPoint,
        old_stack: Stack,
        new_stack: Stack,
        typ: Constructor,
    ):
        assert False
        call_lab, call_ctx = program_point
        old_stack = self.analysis_list[program_point]

        dummy_value = Value()
        addr = record(call_lab, call_ctx)
        cls_value = new_stack.compute_value_of_expr(ast.Name(id="cls", ctx=ast.Load()))
        for c in cls_value:
            instance = typ(addr, c)
            dummy_value.inject_type(instance)
        _, dummy_ret_lab = self.get_func_return_label(call_lab)
        dummy_ret_stmt: ast.Name = self.get_stmt_by_label(dummy_ret_lab)
        new_stack.write_var(dummy_ret_stmt.id, Namespace_Local, dummy_value)
        self.push_info_to_dummy(new_stack, (dummy_ret_lab, call_ctx))

    def _lambda_special_method(
        self,
        program_point: ProgramPoint,
        old_stack,
        new_stack,
        typ: SpecialMethodObject,
    ):
        call_lab, call_ctx = program_point
        call_stmt = self.get_stmt_by_point(program_point)

        dummy_value = Value()
        args, keywords = self.compute_func_args(
            new_stack, call_stmt.args, call_stmt.keywords
        )
        res = typ(*args, **keywords)
        dummy_value.inject_type(res)
        _, dummy_ret_lab = self.get_func_return_label(call_lab)
        dummy_ret_stmt: ast.Name = self.get_stmt_by_label(dummy_ret_lab)
        new_stack.write_var(dummy_ret_stmt.id, Namespace_Local, dummy_value)
        self.push_info_to_dummy(new_stack, (dummy_ret_lab, call_ctx))

    def _lambda_special_init(self, program_point: ProgramPoint, old_stack, new_stack):
        call_lab, call_ctx = program_point
        call_stmt: ast.Call = self.get_stmt_by_label(call_lab)
        assert isinstance(call_stmt, ast.Call) and isinstance(call_stmt.func, ast.Name)

        value: Value = new_stack.compute_value_of_expr(call_stmt.func)
        dummy_value = Value()
        ret_lab, dummy_ret_lab = self.get_init_return_label(call_lab)
        for val in value:
            if isinstance(val, SpecialMethodObject):
                res = val()
                dummy_value.inject_type(res)
            elif isinstance(val, MethodObject):
                entry_lab, exit_lab = val.__my_func__.__my_code__
                instance = val.__my_instance__
                new_ctx: Ctx = merge(call_lab, instance.__my_address__, call_ctx)

                self.entry_info[(entry_lab, new_ctx)] = (
                    instance,
                    INIT_FLAG,
                    val.__my_module__,
                )

                inter_flow = (
                    (call_lab, call_ctx),
                    (entry_lab, new_ctx),
                    (exit_lab, new_ctx),
                    (ret_lab, call_ctx),
                )
                self.inter_flows.add(inter_flow)
        dummy_ret_stmt: ast.Name = self.get_stmt_by_label(dummy_ret_lab)
        new_stack.write_var(dummy_ret_stmt.id, Namespace_Local, dummy_value)
        self.push_info_to_dummy(new_stack, (dummy_ret_lab, call_ctx))

    def _lambda_getter(self, program_point, old_stack, new_stack):
        call_stmt: ast.Attribute = self.get_stmt_by_point(program_point)
        assert isinstance(call_stmt, ast.Attribute), call_stmt

        call_lab, call_ctx = program_point

        value = new_stack.compute_value_of_expr(call_stmt.value)
        dummy_value = Value()
        ret_lab, dummy_ret_lab = self.get_getter_return_label(call_lab)
        for val in value:
            attr_value = my_getattr(val, call_stmt.attr, [])
            for attr_val in attr_value:
                if isinstance(attr_val, DescriptorGetMethod):
                    call_lab, call_ctx = program_point
                    entry_lab, exit_lab = attr_val.__my_func__.__my_code__
                    instance = attr_val.__my_instance__
                    new_ctx: Ctx = merge(call_lab, instance.__my_address__, call_ctx)

                    self.entry_info[(entry_lab, new_ctx)] = (
                        instance,
                        None,
                        attr_val.__my_module__,
                    )

                    inter_flow = (
                        (call_lab, call_ctx),
                        (entry_lab, new_ctx),
                        (exit_lab, new_ctx),
                        (ret_lab, call_ctx),
                    )
                    self.inter_flows.add(inter_flow)
                else:
                    dummy_value.inject_type(attr_val)

        dummy_stmt: ast.Name = self.get_stmt_by_label(dummy_ret_lab)
        new_stack.write_var(dummy_stmt.id, Namespace_Local, dummy_value)
        self.push_info_to_dummy(new_stack, (dummy_ret_lab, call_ctx))

    def _lambda_setter(self, program_point, old_stack, new_stack):
        call_stmt: ast.Assign = self.get_stmt_by_point(program_point)
        assert isinstance(call_stmt, ast.Assign), call_stmt
        assert len(call_stmt.targets) == 1 and isinstance(
            call_stmt.targets[0], ast.Attribute
        )

        attribute: ast.Attribute = call_stmt.targets[0]
        attr: str = call_stmt.targets[0].attr

        call_lab, call_ctx = program_point

        ret_lab, dummy_ret_lab = self.get_setter_return_label(call_lab)
        attr_value = new_stack.compute_value_of_expr(attribute.value)
        expr_value = new_stack.compute_value_of_expr(call_stmt.value)
        for attr_type in attr_value:
            attr_value = my_setattr(attr_type, attr, expr_value)
            for attr_typ in attr_value:
                if isinstance(attr_typ, DescriptorSetMethod):
                    entry_lab, exit_lab = attr_typ.__my_func__.__my_code__
                    instance = attr_typ.__my_instance__
                    new_ctx: Ctx = merge(call_lab, instance.__my_address__, call_ctx)

                    self.entry_info[(entry_lab, new_ctx)] = (
                        instance,
                        None,
                        attr_typ.__my_module__,
                    )

                    inter_flow = (
                        (call_lab, call_ctx),
                        (entry_lab, new_ctx),
                        (exit_lab, new_ctx),
                        (ret_lab, call_ctx),
                    )
                    self.inter_flows.add(inter_flow)

        self.push_info_to_dummy(new_stack, (dummy_ret_lab, call_ctx))

    def push_info_to_dummy(
        self,
        dummy_stack: Stack,
        dummy_point: ProgramPoint,
    ):
        dummy_old_call_stack: Stack = self.analysis_list[dummy_point]
        if not dummy_stack <= dummy_old_call_stack:
            dummy_stack += dummy_old_call_stack
            self.analysis_list[dummy_point] = dummy_stack
            self.LAMBDA(dummy_point)
            added_flows = self.DELTA(dummy_point)
            self.work_list.extendleft(added_flows)

    # deal with cases such as class xxx
    def _lambda_classdef(self, program_point: ProgramPoint, old_stack, new_stack):
        call_lab, call_ctx = program_point

        cfg = self.sub_cfgs[call_lab]
        self.add_sub_cfg(cfg)
        entry_lab = cfg.start_block.bid
        exit_lab = cfg.final_block.bid

        return_lab = self.get_classdef_return_label(call_lab)
        self.inter_flows.add(
            (
                (call_lab, call_ctx),
                (entry_lab, call_ctx),
                (exit_lab, call_ctx),
                (return_lab, call_ctx),
            )
        )
        self.entry_info[(entry_lab, call_ctx)] = (None, None, None)

    # deal with cases such as name()
    def _lambda_normal(self, program_point: ProgramPoint, old_stack, new_stack):

        call_stmt: ast.Call = self.get_stmt_by_point(program_point)
        assert isinstance(call_stmt, ast.Call), call_stmt

        call_lab, call_ctx = program_point
        address = record(call_lab, call_ctx)

        value: Value = new_stack.compute_value_of_expr(call_stmt.func, address)
        # iterate all types to find which is callable
        for typ in value:
            if isinstance(typ, CustomClass):
                self._lambda_class(program_point, old_stack, new_stack, typ)
            elif isinstance(typ, FunctionObject):
                self._lambda_function(program_point, old_stack, new_stack, typ)
            elif isinstance(typ, MethodObject):
                self._lambda_method(program_point, old_stack, new_stack, typ)
            elif isinstance(typ, SpecialMethodObject):
                self._lambda_special_method(program_point, old_stack, new_stack, typ)
            elif isinstance(typ, Constructor):
                self._lambda_constructor(program_point, old_stack, new_stack, typ)
            elif isinstance(typ, BuiltinList):
                self._lambda_builtin_list(program_point, old_stack, new_stack, typ)
            elif isinstance(typ, BuiltinTuple):
                self._lambda_builtin_tuple(program_point, old_stack, new_stack, typ)

    def _lambda_builtin_list(
        self, program_point: ProgramPoint, old_stack, new_stack, typ: BuiltinList
    ):
        call_lab, call_ctx = program_point
        call_stmt = self.get_stmt_by_point(program_point)

        address = record(call_lab, call_ctx)
        args, _ = self.compute_func_args(new_stack, call_stmt.args, call_stmt.keywords)
        dummy_value = Value()
        res = typ(*args)
        res.__my_uuid__ = address
        dummy_value.inject_type(res)
        _, dummy_ret_lab = self.get_func_return_label(call_lab)
        dummy_stmt: ast.Name = self.get_stmt_by_label(dummy_ret_lab)
        new_stack.write_var(dummy_stmt.id, Namespace_Local, dummy_value)
        self.push_info_to_dummy(new_stack, (dummy_ret_lab, call_ctx))

    def _lambda_builtin_tuple(
        self, program_point: ProgramPoint, old_stack, new_stack, typ: BuiltinList
    ):
        call_lab, call_ctx = program_point
        call_stmt = self.get_stmt_by_point(program_point)

        address = record(call_lab, call_ctx)
        args, _ = self.compute_func_args(new_stack, call_stmt.args, call_stmt.keywords)
        dummy_value = Value()
        res = typ(*args)
        res.__my_uuid__ = address
        dummy_value.inject_type(res)
        _, dummy_ret_lab = self.get_func_return_label(call_lab)
        dummy_stmt: ast.Name = self.get_stmt_by_label(dummy_ret_lab)
        new_stack.write_var(dummy_stmt.id, Namespace_Local, dummy_value)
        self.push_info_to_dummy(new_stack, (dummy_ret_lab, call_ctx))

    # deal with class initialization
    # find __new__ and __init__ method
    # then use it to create class instance
    def _lambda_class(self, program_point, old_stack: Stack, new_stack: Stack, typ):
        call_lab, call_ctx = program_point
        addr = record(call_lab, call_ctx)
        new_method = dunder_lookup(typ, "__new__")
        if isinstance(new_method, Constructor):
            instance = new_method(addr, typ)
            value = Value()
            value.inject_type(instance)

            ret_lab, dummy_ret_lab = self.get_new_return_label(call_lab)
            new_stack = deepcopy(old_stack)
            dummy_stmt: ast.Name = self.get_stmt_by_label(dummy_ret_lab)
            new_stack.write_var(dummy_stmt.id, Namespace_Local, value)
            self.push_info_to_dummy(new_stack, (dummy_ret_lab, call_ctx))
        elif isinstance(new_method, FunctionObject):
            entry_lab, exit_lab = new_method.__my_code__
            ret_lab, dummy_ret_lab = self.get_new_return_label(call_lab)
            new_ctx = merge(call_lab, None, call_ctx)
            inter_flow = (
                (call_lab, call_ctx),
                (entry_lab, new_ctx),
                (exit_lab, new_ctx),
                (ret_lab, call_ctx),
            )
            self.inter_flows.add(inter_flow)
            self.entry_info[(entry_lab, new_ctx)] = (typ, None, typ.__my_module__)

    # unbound func call
    # func()
    def _lambda_function(
        self,
        program_point: ProgramPoint,
        old_stack: Stack,
        new_stack: Stack,
        typ: FunctionObject,
    ):
        call_lab, call_ctx = program_point
        entry_lab, exit_lab = typ.__my_code__
        ret_lab, _ = self.get_func_return_label(call_lab)

        new_ctx: Ctx = merge(call_lab, None, call_ctx)
        inter_flow = (
            (call_lab, call_ctx),
            (entry_lab, new_ctx),
            (exit_lab, new_ctx),
            (ret_lab, call_ctx),
        )
        self.inter_flows.add(inter_flow)
        self.entry_info[(entry_lab, new_ctx)] = (None, None, typ.__my_module__)

    def _lambda_method(
        self,
        program_point: ProgramPoint,
        old_stack: Stack,
        new_stack: Stack,
        typ: MethodObject,
    ):
        call_lab, call_ctx = program_point
        entry_lab, exit_lab = typ.__my_func__.__my_code__
        instance = typ.__my_instance__
        new_ctx: Ctx = merge(call_lab, instance.__my_address__, call_ctx)

        ret_lab, dummy_ret_lab = self.get_func_return_label(call_lab)
        self.entry_info[(entry_lab, new_ctx)] = (instance, None, typ.__my_module__)

        inter_flow = (
            (call_lab, call_ctx),
            (entry_lab, new_ctx),
            (exit_lab, new_ctx),
            (ret_lab, call_ctx),
        )
        self.inter_flows.add(inter_flow)

    def transfer(self, program_point: ProgramPoint) -> Stack:
        if self.analysis_list[program_point].is_bot():
            return self.analysis_list[program_point]

        if self.is_dummy_point(program_point):
            return self.transfer_Pass(program_point)
        elif self.is_call_point(program_point):
            return self.transfer_call(program_point)
        elif self.is_entry_point(program_point):
            return self.transfer_entry(program_point)
        elif self.is_exit_point(program_point):
            return self.transfer_exit(program_point)
        elif self.is_return_point(program_point):
            return self.transfer_return(program_point)
        return self.do_transfer(program_point)

    def do_transfer(self, program_point: ProgramPoint) -> Stack:
        stmt: ast.stmt = self.get_stmt_by_point(program_point)
        stmt_name: str = stmt.__class__.__name__
        handler = getattr(self, "transfer_" + stmt_name)
        return handler(program_point)

    def transfer_Assign(self, program_point: ProgramPoint) -> Stack:
        label, context = program_point
        stmt: ast.Assign = self.get_stmt_by_label(label)

        old_stack: Stack = self.analysis_list[program_point]
        new_stack: Stack = deepcopy(old_stack)

        rhs_value: Value = new_stack.compute_value_of_expr(stmt.value, program_point)
        target: ast.expr = stmt.targets[0]
        if isinstance(target, ast.Name):
            new_stack.write_var(target.id, Namespace_Local, rhs_value)
        else:
            assert False
        return new_stack

    def transfer_AugAssign(self, program_point: ProgramPoint):
        label, context = program_point
        stmt: ast.AugAssign = self.get_stmt_by_label(label)

        old: Stack = self.analysis_list[program_point]
        new: Stack = deepcopy(old)

        lhs_value: Value = new.compute_value_of_expr(stmt.target)
        rhs_value: Value = new.compute_value_of_expr(stmt.value)
        lhs_value += rhs_value

        return new

    def transfer_call(self, program_point: ProgramPoint):
        call_lab, _ = program_point
        if self.is_classdef_call_label(call_lab):
            return self._transfer_call_classdef(program_point)
        elif self.is_normal_call_label(call_lab):
            return self._transfer_call_normal(program_point)
        elif self.is_special_init_call_label(call_lab):
            return self._transfer_call_normal(program_point)
        elif self.is_getter_call_label(call_lab):
            return self._transfer_call_getter(program_point)
        elif self.is_setter_call_label(call_lab):
            return self._transfer_call_setter(program_point)

    def _transfer_call_classdef(self, program_point: ProgramPoint):
        old: Stack = self.analysis_list[program_point]
        new: Stack = deepcopy(old)
        new.next_ns()
        return new

    def _transfer_call_normal(self, program_point: ProgramPoint):
        call_lab, _ = program_point
        call_stmt: ast.stmt = self.get_stmt_by_label(call_lab)
        assert isinstance(call_stmt, ast.Call), call_stmt

        old_stack: Stack = self.analysis_list[program_point]
        new_stack: Stack = deepcopy(old_stack)
        new_stack.next_ns()

        args = call_stmt.args
        idx = 0
        for idx, arg in enumerate(args, 1):
            arg_value = new_stack.compute_value_of_expr(arg)
            new_stack.write_var(str(idx), Namespace_Local, arg_value)
        new_stack.write_var(POSITION_FLAG, Namespace_Helper, idx)

        keywords = call_stmt.keywords
        for keyword in keywords:
            keyword_value = new_stack.compute_value_of_expr(keyword.value)
            new_stack.write_var(keyword.arg, Namespace_Local, keyword_value)

        return new_stack

    def _transfer_call_getter(self, program_point: ProgramPoint):
        call_lab, _ = program_point
        call_stmt: ast.stmt = self.get_stmt_by_label(call_lab)
        assert isinstance(call_stmt, ast.Attribute), call_stmt

        old_stack: Stack = self.analysis_list[program_point]
        new_stack = deepcopy(old_stack)
        new_stack.next_ns()

        target_value = old_stack.compute_value_of_expr(call_stmt.value)
        ret_value = Value()
        for target_typ in target_value:
            attr_value = my_getattr(target_typ, call_stmt.attr, None)
            for attr_typ in attr_value:
                if isinstance(attr_typ, DescriptorGetMethod):
                    instance = attr_typ.desc_instance
                    instance_value = create_value_with_type(instance)
                    new_stack.write_var("1", Namespace_Local, instance_value)
                    owner = attr_typ.desc_owner
                    owner_value = create_value_with_type(owner)
                    new_stack.write_var("2", Namespace_Local, owner_value)
                    new_stack.write_var(POSITION_FLAG, Namespace_Helper, 2)
                else:
                    ret_value.inject_type(attr_typ)

        ret_lab, _ = self.get_getter_return_label(call_lab)
        ret_stmt: ast.Name = self.get_stmt_by_label(ret_lab)
        new_stack.write_var(ret_stmt.id, Namespace_Local, ret_value)
        return new_stack

    def _transfer_call_setter(self, program_point: ProgramPoint):
        call_lab, _ = program_point
        call_stmt: ast.stmt = self.get_stmt_by_label(call_lab)
        assert isinstance(call_stmt, ast.Assign)
        assert len(call_stmt.targets) == 1 and isinstance(
            call_stmt.targets[0], ast.Attribute
        )

        attribute: ast.Attribute = call_stmt.targets[0]
        attr: str = call_stmt.targets[0].attr

        old_stack: Stack = self.analysis_list[program_point]
        new_stack = deepcopy(old_stack)
        lhs_value = new_stack.compute_value_of_expr(attribute.value)
        rhs_value = new_stack.compute_value_of_expr(call_stmt.value)
        for target_typ in lhs_value:
            attr_value = my_setattr(target_typ, attr, rhs_value)
            if attr_value is not None:
                for attr_typ in attr_value:
                    if isinstance(attr_typ, DescriptorSetMethod):
                        instance = attr_typ.desc_instance
                        setter_instance = create_value_with_type(instance)
                        new_stack.write_var("1", Namespace_Local, setter_instance)
                        desc_value = attr_typ.desc_value
                        setter_value = create_value_with_type(desc_value)
                        new_stack.write_var("2", Namespace_Local, setter_value)
                        new_stack.write_var(POSITION_FLAG, Namespace_Helper, 2)

        return new_stack

    # consider current global namespace
    def transfer_entry(self, program_point: ProgramPoint):
        entry_lab, entry_ctx = program_point
        stmt = self.get_stmt_by_label(entry_lab)
        old: Stack = self.analysis_list[program_point]
        new: Stack = deepcopy(old)

        # is self.self_info[program_point] is not None, it means
        # this is a class method call
        # we pass instance information, module name to entry labels
        instance, init_flag, module_name = self.entry_info[program_point]
        if instance:
            value = Value()
            value.inject_type(instance)
            new.write_var(str(0), Namespace_Local, value)
        if init_flag:
            new.write_var(INIT_FLAG, Namespace_Helper, mock_value)
        if module_name:
            new.check_module_diff(module_name)

        if isinstance(stmt, ast.arguments):
            arguments = stmt
            # Positional and keyword arguments
            args = arguments.args
            arg_flags = [False for _ in args]
            # if it has an instance, self is considered
            start_pos = 0 if instance else 1
            arg_pos = 0

            f_locals: Namespace = new.top_frame().f_locals

            positional_len = f_locals.read_value(POSITION_FLAG)
            for position in range(start_pos, positional_len + 1):
                parameter = args[arg_pos].arg
                parameter_value = f_locals.read_value(str(position))
                new.write_var(parameter, Namespace_Local, parameter_value)

                arg_flags[arg_pos] = True
                arg_pos += 1

            # keyword arguments
            for idx, elt in enumerate(arg_flags):
                if not elt:
                    arg_name = args[idx].arg
                    if arg_name in f_locals:
                        arg_flags[idx] = True

            # default arguments
            for idx, elt in enumerate(arg_flags):
                if not elt:
                    arg_name = args[idx].arg
                    default = arguments.defaults[idx]
                    assert default is not None
                    new.write_var(arg_name, Namespace_Local, default)

        return new

    def transfer_exit(self, program_point: ProgramPoint):
        old: Stack = self.analysis_list[program_point]
        new: Stack = deepcopy(old)

        if not new.top_namespace_contains(RETURN_FLAG):
            value = Value()
            value.inject_type(NoneType())
            new.write_var(RETURN_FLAG, Namespace_Local, value)

        return new

    def transfer_return(self, program_point: ProgramPoint):
        return_lab, return_ctx = program_point
        stmt: ast.stmt = self.get_stmt_by_label(return_lab)

        if isinstance(stmt, ast.ClassDef):
            return self.transfer_return_classdef(program_point)
        elif isinstance(stmt, ast.Name):
            return self.transfer_return_name(program_point, stmt)
        else:
            assert False

    def transfer_return_name(self, program_point: ProgramPoint, stmt: ast.Name):
        old: Stack = self.analysis_list[program_point]
        new: Stack = deepcopy(old)
        return_value: Value = new.read_var(RETURN_FLAG)
        new.pop_frame()

        # no need to assign
        if stmt.id == Unused_Name:
            return new

        if old.top_namespace_contains(INIT_FLAG):
            return_value = old.read_var("self")
        # write value to name
        new.write_var(stmt.id, Namespace_Local, return_value)
        return new

    def transfer_Import(self, program_point: ProgramPoint):
        lab, ctx = program_point
        old: Stack = self.analysis_list[program_point]
        new: Stack = deepcopy(old)
        stmt: ast.Import = self.get_stmt_by_label(lab)
        module_name = stmt.names[0].name
        as_name = stmt.names[0].asname
        mod = dmf.share.static_import_module(module_name)
        value = Value()
        value.inject_type(mod)
        new.write_var(module_name if as_name is None else as_name, value)
        logger.debug("Import module {}".format(mod))
        return new

    def transfer_ImportFrom(self, program_point: ProgramPoint):
        lab, ctx = program_point
        old: Stack = self.analysis_list[program_point]
        new: Stack = deepcopy(old)
        stmt: ast.ImportFrom = self.get_stmt_by_label(lab)

        module_name = "" if stmt.module is None else stmt.module
        dot_number = "." * stmt.level
        package = new.read_package()
        mod = dmf.share.static_import_module(
            name=dot_number + module_name,
            package=package,
        )
        logger.debug("ImportFrom module {}".format(mod))

        aliases = stmt.names
        for alias in aliases:
            imported_name = alias.name
            imported_value = mod.getattr(imported_name)
            if alias.asname is None:
                new.write_var(imported_name, Namespace_Local, imported_value)
            else:
                new.write_var(alias.asname, Namespace_Local, imported_value)
        return new

    def transfer_return_classdef(self, program_point: ProgramPoint):
        # return stuff
        return_lab, return_ctx = program_point
        # stmt
        stmt: ast.ClassDef = self.get_stmt_by_label(return_lab)
        # return state
        return_state: Stack = self.analysis_list[program_point]

        new_return_state: Stack = deepcopy(return_state)
        new_return_state.pop_frame()

        # class name
        cls_name: str = stmt.name
        module: str = new_return_state.read_module()
        # class frame
        frame: Frame = return_state.top_frame()

        def compute_bases(statement: ast.ClassDef):
            if statement.bases:
                base_types = []
                for base in statement.bases:
                    assert isinstance(base, ast.Name)
                    base_value: Value = new_return_state.read_var(base.id)
                    cls_types: List[CustomClass] = base_value.extract_cls_type()
                    assert len(cls_types) == 1
                    for cls in cls_types:
                        base_types.append(cls)
                return base_types
            else:
                default_base = my_object
                return [default_base]

        value: Value = Value()
        bases = compute_bases(stmt)
        call_lab = self.get_classdef_call_label(return_lab)
        custom_class: CustomClass = CustomClass(
            uuid=call_lab,
            name=cls_name,
            module=module,
            bases=bases,
            namespace=frame.f_locals,
        )
        value.inject_type(custom_class)
        new_return_state.write_var(cls_name, Namespace_Local, value)
        return new_return_state

    def transfer_FunctionDef(self, program_point: ProgramPoint):
        lab, _ = program_point
        stmt: ast.FunctionDef = self.get_stmt_by_label(lab)
        func_cfg: CFG = self.sub_cfgs[lab]
        self.add_sub_cfg(func_cfg)

        old: Stack = self.analysis_list[program_point]
        new: Stack = deepcopy(old)

        func_name: str = stmt.name
        args: ast.arguments = stmt.args

        diff = len(args.args) - len(args.defaults)
        diff_none = [None] * diff
        args.defaults = diff_none + args.defaults
        for idx, default in enumerate(args.defaults):
            args.defaults[idx] = (
                None if default is None else new.compute_value_of_expr(default)
            )

        func_module: str = new.read_module()
        entry_lab, exit_lab = func_cfg.start_block.bid, func_cfg.final_block.bid

        value = Value()
        value.inject_type(
            FunctionObject(
                uuid=lab, name=func_name, module=func_module, code=(entry_lab, exit_lab)
            )
        )

        new.write_var(func_name, Namespace_Local, value)
        return new

    def transfer_Pass(self, program_point: ProgramPoint) -> Stack:
        old: Stack = self.analysis_list[program_point]
        new: Stack = deepcopy(old)
        return new

    def transfer_If(self, program_point: ProgramPoint) -> Stack:
        return self.transfer_Pass(program_point)

    def transfer_While(self, program_point: ProgramPoint) -> Stack:
        return self.transfer_Pass(program_point)

    def transfer_Return(self, program_point: ProgramPoint) -> Stack:
        lab, _ = program_point
        stmt: ast.Return = self.get_stmt_by_label(lab)

        old: Stack = self.analysis_list[program_point]
        new: Stack = deepcopy(old)

        assert isinstance(stmt.value, ast.Name)
        name: str = stmt.value.id
        value: Value = new.read_var(name)
        new.write_var(RETURN_FLAG, Namespace_Local, value)
        return new

    def transfer_Global(self, program_point: ProgramPoint) -> Stack:
        lab, _ = program_point
        stmt = self.get_stmt_by_label(lab)

        old: Stack = self.analysis_list[program_point]
        new: Stack = deepcopy(old)

        name = stmt.names[0]
        new.write_var(name, Namespace_Global, None)

        return new

    def transfer_Nonlocal(self, program_point: ProgramPoint) -> Stack:
        lab, _ = program_point
        stmt = self.get_stmt_by_label(lab)

        old: Stack = self.analysis_list[program_point]
        new: Stack = deepcopy(old)

        name = stmt.names[0]
        new.write_var(name, Namespace_Nonlocal, None)

        return new
