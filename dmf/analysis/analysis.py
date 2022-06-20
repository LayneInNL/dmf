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
from dmf.analysis.prim import Int, Bool, NoneType
from dmf.analysis.stack import Frame, Stack, stack_bot_builder
from dmf.analysis.value import (
    Unused_Name,
    ModuleType,
    SuperIns,
    analysis_heap,
    CustomClass,
    Instance,
    my_getattr,
    FunctionClass,
    FunctionObject,
    my_object,
    SpecialFunctionObject,
    MethodObject,
    SpecialMethodObject,
    find_magic_method_in_mro,
    Constructor,
)
from dmf.analysis.value import (
    Value,
    RETURN_FLAG,
    INIT_FLAG,
    SELF_FLAG,
    INIT_FLAG_VALUE,
)
from dmf.flows import CFG
from dmf.flows.flows import BasicBlock
from dmf.log.logger import logger

Empty_Ctx = ()
Ctx = Tuple
Heap = int
Lab = int
Basic_Flow = Tuple[Lab, Lab]
ProgramPoint = Tuple[Lab, Ctx]
Flow = Tuple[ProgramPoint, ProgramPoint]
Inter_Flow = Tuple[ProgramPoint, ProgramPoint, ProgramPoint, ProgramPoint]


def record(label: Lab, context: Ctx):
    return label


def merge(label: Lab, heap, context: Ctx):
    return context[-1:] + (label,)


class Base:
    def __init__(self):
        self.flows: Set[Basic_Flow] = dmf.share.flows
        self.call_return_flows: Set[Basic_Flow] = dmf.share.call_return_flows
        self.blocks: Dict[Lab, BasicBlock] = dmf.share.blocks
        self.sub_cfgs: Dict[Lab, CFG] = dmf.share.sub_cfgs
        self.inter_flows: Set[Inter_Flow] = set()

    def get_stmt_by_label(self, label: Lab):
        return self.blocks[label].stmt[0]

    def is_call_label(self, label: Lab):
        for call_label, _ in self.call_return_flows:
            if label == call_label:
                return True
        return False

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

    def is_return_label(self, label):
        for _, return_label in self.call_return_flows:
            if label == return_label:
                return True
        return False

    def get_call_label(self, label):
        for call_label, return_label in self.call_return_flows:
            if label == return_label:
                return call_label

    def get_call_point(self, program_point):
        for call_point, _, _, return_point in self.inter_flows:
            if program_point == return_point:
                return call_point

    def get_return_label(self, label):
        for call_label, return_label in self.call_return_flows:
            if label == call_label:
                return return_label

    def add_sub_cfg(self, cfg: CFG):
        self.blocks.update(cfg.blocks)
        self.flows.update(cfg.flows)
        self.sub_cfgs.update(cfg.sub_cfgs)
        self.call_return_flows.update(cfg.call_return_flows)

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
        self.entry_info: Dict[
            ProgramPoint, Tuple[Instance | None, str | None, str | None]
        ] = {}
        self.work_list: Deque[Flow] = deque()
        self.analyzed_program_points = None
        self.analysis_list = None
        self.analysis_effect_list = None
        self.extremal_value: Stack = Stack()

        curr_module: ModuleType = dmf.share.analysis_modules[module_name]
        start_lab, final_lab = curr_module.entry_label, curr_module.exit_label
        self.extremal_point: ProgramPoint = (start_lab, Empty_Ctx)
        self.final_point: ProgramPoint = (final_lab, Empty_Ctx)

        # init first frame
        def init_first_frame(extremal_value, module):
            global_ns = module.namespace
            builtins_ns = None
            extremal_value.push_frame(
                Frame(
                    f_locals=global_ns,
                    f_back=None,
                    f_globals=global_ns,
                    f_builtins=builtins_ns,
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

    # based on current program point, update self.IF
    def LAMBDA(self, program_point: ProgramPoint) -> None:
        lab, ctx = program_point

        # we are only interested in call labels
        if not self.is_call_label(lab):
            return

        stmt = self.get_stmt_by_label(lab)

        assert isinstance(stmt, (ast.ClassDef, ast.Call)), stmt

        # class
        if isinstance(stmt, ast.ClassDef):
            self.lambda_classdef(program_point)
        # procedural call
        elif isinstance(stmt, ast.Call):
            assert isinstance(stmt.func, ast.Name), stmt
            has_info = self.lambda_name(program_point, stmt.func)
            additional_value = Value()
            if not has_info:
                if stmt.func.id == "object":
                    address = record(lab, ctx)
                    instance = Instance(address=address, cls=my_object)
                    additional_value.inject_type(instance)
                    self.transfer_no_edge_values(program_point, additional_value)

    # deal with cases such as class xxx
    def lambda_classdef(self, program_point: ProgramPoint):
        call_lab, call_ctx = program_point

        cfg = self.sub_cfgs[call_lab]
        self.add_sub_cfg(cfg)
        entry_lab = cfg.start_block.bid
        exit_lab = cfg.final_block.bid

        return_lab = self.get_return_label(call_lab)
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
    def lambda_name(self, program_point: ProgramPoint, name):
        has_info = False

        call_lab, call_ctx = program_point
        address = record(call_lab, call_ctx)

        stack: Stack = self.analysis_list[program_point]
        try:
            # get abstract value of name
            value: Value = stack.compute_value_of_expr(name, address)
        except:
            logger.critical("No attribute named {}".format(name))
        else:
            has_info = True
            # iterate all types to find which is callable
            for _, typ in value:
                if isinstance(typ, CustomClass):
                    self.lambda_class(program_point, typ)
                elif isinstance(typ, FunctionObject):
                    self.lambda_function(program_point, typ)
                elif isinstance(typ, MethodObject):
                    self.lambda_method(program_point, typ)
                else:
                    assert False, typ
        finally:
            return has_info

    def merge_no_edge_values(self, typ, value: Value):
        value.inject_type(typ)

    def transfer_no_edge_values(self, call_program_point: ProgramPoint, value: Value):
        call_lab, call_ctx = call_program_point
        old = self.analysis_list[call_program_point]

        return_lab = self.get_return_label(call_lab)
        return_stmt: ast.Name = self.get_stmt_by_label(return_lab)
        return_program_point = (return_lab, call_ctx)
        self.LAMBDA(return_program_point)
        added_flows = self.DELTA(return_program_point)
        assert len(added_flows) == 1

        return_next_program_point = added_flows[0][1]
        old_return_next_stack = self.analysis_list[return_next_program_point]

        fake_return_stack = deepcopy(old)
        if return_stmt.id != Unused_Name:
            fake_return_stack.write_var(return_stmt.id, value)
        if not fake_return_stack <= old_return_next_stack:
            fake_return_stack += old_return_next_stack
            self.analysis_list[return_next_program_point] = fake_return_stack
            self.analyzed_program_points.add(return_next_program_point)
            self.LAMBDA(return_next_program_point)
            added_flows = self.DELTA(return_next_program_point)
            self.work_list.extendleft(added_flows)

    # deal with class initialization
    # find __new__ and __init__ method
    # then use it to create class instance
    def lambda_class(self, program_point, typ):
        call_lab, call_ctx = program_point
        return_lab = self.get_return_label(call_lab)
        addr = record(call_lab, call_ctx)
        new_method = find_magic_method_in_mro(typ, "__new__")
        if isinstance(new_method, Constructor):
            instance = new_method(addr, typ)
        elif isinstance(new_method, FunctionObject):
            assert False
        additional_values = Value()

        init_function = find_magic_method_in_mro(typ, "__init__")
        if isinstance(init_function, FunctionObject):
            entry_lab, exit_lab = init_function.__my_code__
            inter_flow = (
                (call_lab, call_ctx),
                (entry_lab, call_ctx),
                (exit_lab, call_ctx),
                (return_lab, call_ctx),
            )
            self.inter_flows.add(inter_flow)
            self.entry_info[(entry_lab, call_ctx)] = (
                instance,
                INIT_FLAG,
                init_function.__my_module__,
            )
        elif isinstance(init_function, SpecialFunctionObject):
            res = init_function(instance)
            self.merge_no_edge_values(res, additional_values)
        else:
            logger.critical(new_method)
            assert False
        self.transfer_no_edge_values(program_point, additional_values)

    # unbound func call
    # func()
    def lambda_function(self, program_point: ProgramPoint, typ: FunctionObject):
        call_lab, call_ctx = program_point
        entry_lab, exit_lab = typ.code
        return_lab = self.get_return_label(call_lab)
        new_ctx: Ctx = merge(call_lab, None, call_ctx)
        inter_flow = (
            (call_lab, call_ctx),
            (entry_lab, new_ctx),
            (exit_lab, new_ctx),
            (return_lab, call_ctx),
        )
        self.inter_flows.add(inter_flow)
        self.entry_info[(entry_lab, new_ctx)] = (None, None, typ.__my_module__)

    def lambda_method(self, program_point: ProgramPoint, typ: MethodObject):
        call_lab, call_ctx = program_point
        entry_lab, exit_lab = typ.code
        return_lab = self.get_return_label(call_lab)

        instance = typ.instance
        new_ctx: Ctx = merge(call_lab, instance, call_ctx)
        inter_flow = (
            (call_lab, call_ctx),
            (entry_lab, new_ctx),
            (exit_lab, new_ctx),
            (return_lab, call_ctx),
        )
        self.inter_flows.add(inter_flow)
        self.entry_info[(entry_lab, new_ctx)] = (instance, None, typ.module)

    def transfer(self, program_point: ProgramPoint) -> Stack:
        lab, _ = program_point
        if self.analysis_list[program_point].is_bot():
            return self.analysis_list[program_point]

        if self.is_call_label(lab):
            return self.transfer_call(program_point)
        elif self.is_entry_point(program_point):
            return self.transfer_entry(program_point)
        elif self.is_exit_point(program_point):
            return self.transfer_exit(program_point)
        elif self.is_return_label(lab):
            return self.transfer_return(program_point)
        return self.do_transfer(program_point)

    def do_transfer(self, program_point: ProgramPoint) -> Stack:
        label, _ = program_point
        stmt: ast.stmt = self.get_stmt_by_label(label)
        stmt_name: str = stmt.__class__.__name__
        handler = getattr(self, "transfer_" + stmt_name)
        return handler(program_point)

    def transfer_Assign(self, program_point: ProgramPoint) -> Stack:
        label, context = program_point
        stmt: ast.Assign = self.get_stmt_by_label(label)

        old: Stack = self.analysis_list[program_point]
        new: Stack = deepcopy(old)

        rhs_value: Value = new.compute_value_of_expr(stmt.value, program_point)
        target: ast.expr = stmt.targets[0]
        if isinstance(target, ast.Name):
            lhs_name: str = target.id
            new.write_var(lhs_name, rhs_value)
        elif isinstance(target, ast.Attribute):
            assert isinstance(target.value, ast.Name)
            lhs_name: str = target.value.id
            value: Value = new.read_var(lhs_name)
            field: str = target.attr
            for lab, typ in value:
                if isinstance(typ, Instance):
                    analysis_heap.write_field_to_heap(typ, field, rhs_value)
                elif isinstance(typ, CustomClass):
                    pass
                elif isinstance(typ, FunctionObject):
                    pass
                elif isinstance(typ, (Int, Bool, NoneType)):
                    pass
                else:
                    assert False
        else:
            assert False
        return new

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
        call_lab, call_ctx = program_point
        stmt: ast.stmt = self.get_stmt_by_label(call_lab)
        if isinstance(stmt, ast.ClassDef):
            old: Stack = self.analysis_list[program_point]
            new: Stack = deepcopy(old)
            new.next_ns()
            return new
        elif isinstance(stmt, ast.Call):
            old: Stack = self.analysis_list[program_point]
            new: Stack = deepcopy(old)
            func_value: Value = new.compute_value_of_expr(stmt.func)

            new.next_ns()
            for _, typ in func_value:
                # __init__ or instance method
                if isinstance(
                    typ, (CustomClass, MethodObject, FunctionObject, FunctionClass)
                ):
                    args = stmt.args
                    if args:
                        for idx, arg in enumerate(args, 1):
                            arg_value = new.compute_value_of_expr(arg)
                            new.write_var(str(idx), arg_value)
                        new.write_special_var("__positional__", idx)
                    else:
                        new.write_special_var("__positional__", 0)
                    keywords = stmt.keywords
                    for keyword in keywords:
                        keyword_value = new.compute_value_of_expr(keyword.value)
                        new.write_var(keyword.arg, keyword_value)
                elif isinstance(typ, SuperIns):
                    return_label = self.get_return_label(call_lab)
                    return_stmt: ast.Name = self.get_stmt_by_label(return_label)
                    fake_return_stack = deepcopy(old)
                    value = Value()
                    value.inject_type(typ)
                    fake_return_stack.write_var(return_stmt.id, value)
                    old_return_stack = self.analysis_list[(return_label, call_ctx)]
                    if not fake_return_stack <= old_return_stack:
                        fake_return_stack += old_return_stack
                        self.analysis_list[(return_label, call_ctx)] = fake_return_stack
                    self.LAMBDA((return_label, call_ctx))
                    added_flows = self.DELTA((return_label, call_ctx))
                    assert len(added_flows) == 1
                    old_return_stack = deepcopy(
                        self.analysis_list[(return_label, call_ctx)]
                    )
                    old_return_next_stack = self.analysis_list[added_flows[0][1]]
                    if not old_return_stack <= old_return_next_stack:
                        old_return_stack += old_return_next_stack
                        self.analysis_list[added_flows[0][1]] = old_return_stack
                        self.LAMBDA(added_flows[0][1])
                        added_flows = self.DELTA(added_flows[0][1])
                        self.work_list.extendleft(added_flows)
                else:
                    assert False
            return new
        else:
            assert False

    # consider current global namespace
    def transfer_entry(self, program_point: ProgramPoint):
        entry_lab, entry_ctx = program_point
        stmt = self.get_stmt_by_label(entry_lab)
        old: Stack = self.analysis_list[program_point]
        new: Stack = deepcopy(old)

        # is self.self_info[program_point] is not None, it means
        # this is a class method call
        # we pass instance information, INIT information and module name to entry labels
        instance, init_flag, module_name = self.entry_info[program_point]
        if instance:
            instance_value = Value()
            instance_value.inject_type(instance)
            # new.write_var_to_stack(SELF_FLAG, value)
            new.write_var(str(0), instance_value)
        if init_flag:
            # write the init flag to stack
            new.write_var(INIT_FLAG, INIT_FLAG_VALUE)
        if module_name:
            new.check_module_diff(module_name)

        if isinstance(stmt, ast.Pass):
            return new
        elif isinstance(stmt, ast.arguments):
            arguments = stmt

            # Positional and keyword arguments
            args = arguments.args
            arg_flags = [False for _ in args]
            # if it has an instance, self is considered
            start_pos = 0 if instance else 1
            arg_pos = 0
            positional_len = new.read_special_attribute("__positional__")
            for position in range(start_pos, positional_len + 1):
                parameter = args[arg_pos].arg
                parameter_value = new.read_var(str(position))
                arg_flags[arg_pos] = True
                new.write_var(parameter, parameter_value)
                arg_pos += 1

            # keyword arguments
            for idx, elt in enumerate(arg_flags):
                if not elt:
                    arg_name = args[idx].arg
                    if new.top_frame_contains(arg_name):
                        arg_flags[idx] = True

            # default arguments
            for idx, elt in enumerate(arg_flags):
                if not elt:
                    arg_name = args[idx].arg
                    default = arguments.value_defaults[idx]
                    if default is None:
                        assert False
                    else:
                        new.write_var(arg_name, default)

            return new
        else:
            logger.error(stmt)
            assert False

    def transfer_exit(self, program_point: ProgramPoint):
        old: Stack = self.analysis_list[program_point]
        new: Stack = deepcopy(old)

        if not new.top_frame_contains(RETURN_FLAG):
            value = Value(NoneType())
            new.write_var(RETURN_FLAG, value)

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
        before_return_stack: Stack = self.analysis_list[program_point]
        after_return_stack: Stack = deepcopy(before_return_stack)
        return_value: Value = after_return_stack.read_var(RETURN_FLAG)
        if after_return_stack.top_frame_contains(INIT_FLAG):
            return_value: Value = after_return_stack.read_var(SELF_FLAG)
        after_return_stack.pop_frame()

        # no need to assign
        if stmt.id == Unused_Name:
            return after_return_stack

        # write value to name
        after_return_stack.write_var(stmt.id, return_value)
        return after_return_stack

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
        package = new.get_top_frame_package()
        mod = dmf.share.static_import_module(
            name=dot_number + module_name,
            package=package,
        )
        logger.debug("ImportFrom module {}".format(mod))

        aliases = stmt.names
        for alias in aliases:
            imported_name = alias.name
            var_scope, imported_value = mod.getattr(imported_name)
            if alias.asname is None:
                new.write_var(imported_name, imported_value)
            else:
                new.write_var(alias.asname, imported_value)
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
        module: str = new_return_state.get_top_frame_module()
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
        call_lab = self.get_call_label(return_lab)
        custom_class: CustomClass = CustomClass(
            uuid=call_lab,
            name=cls_name,
            module=module,
            bases=bases,
            namespace=frame.f_locals,
        )
        # cls_type: ClsType = ClsType(call_lab, cls_name, module, bases, frame.f_locals)
        # value.inject_type(cls_type)
        value.inject_type(custom_class)
        new_return_state.write_var(cls_name, value)
        return new_return_state

    def transfer_FunctionDef(self, program_point: ProgramPoint):
        lab, _ = program_point
        stmt: ast.FunctionDef = self.get_stmt_by_label(lab)
        func_cfg: CFG = self.sub_cfgs[lab]
        self.add_sub_cfg(func_cfg)

        old: Stack = self.analysis_list[program_point]
        new: Stack = deepcopy(old)

        func_name: str = stmt.name
        func_args: ast.arguments = stmt.args
        value_defaults = [
            new.compute_value_of_expr(default) for default in func_args.defaults
        ]
        if len(func_args.args) != len(value_defaults):
            diff = len(func_args.args) - len(value_defaults)
            diff_none = [None] * diff
            func_args.value_defaults = diff_none + value_defaults
        func_module: str = new.get_top_frame_module()
        entry_lab, exit_lab = func_cfg.start_block.bid, func_cfg.final_block.bid

        value = Value()
        function = FunctionObject(
            uuid=lab, name=func_name, module=func_module, code=(entry_lab, exit_lab)
        )
        value.inject_type(function)

        new.write_var(func_name, value)
        return new

    def transfer_Pass(self, program_point: ProgramPoint) -> Stack:
        old: Stack = self.analysis_list[program_point]
        new: Stack = deepcopy(old)
        return new

    def transfer_If(self, program_point: ProgramPoint) -> Stack:
        old: Stack = self.analysis_list[program_point]
        new: Stack = deepcopy(old)
        return new

    def transfer_While(self, program_point: ProgramPoint) -> Stack:
        old: Stack = self.analysis_list[program_point]
        new: Stack = deepcopy(old)
        return new

    def transfer_Return(self, program_point: ProgramPoint) -> Stack:
        lab, _ = program_point
        stmt: ast.Return = self.get_stmt_by_label(lab)

        old: Stack = self.analysis_list[program_point]
        new: Stack = deepcopy(old)

        assert isinstance(stmt.value, ast.Name)
        name: str = stmt.value.id
        value: Value = new.read_var(name)
        # get return value
        # if it's init, return self
        if new.top_frame_contains(INIT_FLAG):
            value = new.read_var(SELF_FLAG)
        new.write_var(RETURN_FLAG, value)
        return new

    def transfer_Global(self, program_point: ProgramPoint) -> Stack:
        lab, _ = program_point
        stmt: ast.Global = self.get_stmt_by_label(lab)

        old: Stack = self.analysis_list[program_point]
        new: Stack = deepcopy(old)

        name = stmt.names[0]
        value = new.read_var(name, scope="global")
        new.write_var(name, value, "global")

        return new

    def transfer_Nonlocal(self, program_point: ProgramPoint) -> Stack:
        lab, _ = program_point
        stmt: ast.Nonlocal = self.get_stmt_by_label(lab)

        old: Stack = self.analysis_list[program_point]
        new: Stack = deepcopy(old)

        name = stmt.names[0]
        value = new.read_var(name)
        new.write_var(name, value, "nonlocal")

        return new
