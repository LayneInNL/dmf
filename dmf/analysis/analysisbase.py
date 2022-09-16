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
import sys
from typing import Set, Tuple, Dict

from dmf.flows import CFG
from dmf.flows.flows import BasicBlock
from dmf.log.logger import logger

ProgramPoint = Tuple[int, Tuple]


class AnalysisBase:
    def __init__(self):
        self.flows: Set[Tuple[int, int]] = sys.analysis_flows
        self.blocks: Dict[int, BasicBlock] = sys.analysis_blocks
        self.sub_cfgs: Dict[int, CFG] = sys.analysis_cfgs

        self.dummy_labels = sys.dummy_labels
        self.call_labels = sys.call_labels
        self.return_labels = sys.return_labels
        self.call_return_inter_flows = sys.call_flow_tuples
        self.classdef_inter_flows = sys.classdef_flow_tuples
        self.magic_right_inter_flows = sys.magic_right_inter_tuples
        self.magic_left_inter_flows = sys.magic_left_inter_tuples
        self.magic_del_inter_flows = sys.magic_del_inter_tuples
        self.special_init_flows = sys.special_init_inter_flows

        self.inter_flows: Set[
            Tuple[ProgramPoint, ProgramPoint, ProgramPoint, ProgramPoint]
        ] = set()

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

    def is_class_init_call_point(self, program_point: ProgramPoint):
        label, _ = program_point
        return self.is_special_init_call_label(label)

    def is_right_magic_call_label(self, label):
        for call, *_ in self.magic_right_inter_flows:
            if label == call:
                return True
        return False

    def is_right_magic_call_point(self, program_point: ProgramPoint):
        label, _ = program_point
        return self.is_right_magic_call_label(label)

    def is_del_magic_call_label(self, label):
        for call, *_ in self.magic_del_inter_flows:
            if label == call:
                return True
        return False

    def is_del_magic_call_point(self, program_point: ProgramPoint):
        label, _ = program_point
        return self.is_del_magic_call_label(label)

    def is_left_magic_call_label(self, label):
        for call, *_ in self.magic_left_inter_flows:
            if label == call:
                return True
        return False

    def is_left_magic_call_point(self, program_point: ProgramPoint):
        label, _ = program_point
        return self.is_left_magic_call_label(label)

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

    def get_right_magic_return_label(self, label):
        for (
            call_label,
            return_label,
            dummy_return_label,
        ) in self.magic_right_inter_flows:
            if label == call_label:
                return return_label, dummy_return_label
        raise KeyError

    def get_del_magic_return_label(self, label):
        for call_label, return_label, dummy_return_label in self.magic_del_inter_flows:
            if label == call_label:
                return return_label, dummy_return_label
        raise KeyError

    def get_left_magic_return_label(self, label):
        for call_label, return_label, dummy_return_label in self.magic_left_inter_flows:
            if label == call_label:
                return return_label, dummy_return_label
        raise KeyError

    def get_special_new_return_label(self, label):
        for (
            new,
            new_return,
            new_dummy_return,
            init_lookup,
            init_lookup_return,
            init_lookup_dummy_return,
            deleted_first_var,
            init_call,
            init_call_return,
            deleted_second_var,
            init_call_dummy_return,
        ) in self.call_return_inter_flows:
            if label == new:
                return new_return, new_dummy_return
        raise KeyError

    def get_func_return_label(self, label):
        for (
            new,
            new_return,
            new_dummy_return,
            init_lookup,
            init_lookup_return,
            init_lookup_dummy_return,
            deleted_first_var,
            init_call,
            init_call_return,
            deleted_second_var,
            init_call_dummy_return,
        ) in self.call_return_inter_flows:
            if label == new:
                return init_call_return, init_call_dummy_return
        raise KeyError

    def get_special_init_return_label(self, label):
        for l1, l2, l3 in self.special_init_flows:
            if label == l1:
                return l2, l3
        raise KeyError

    def add_sub_cfg(self, lab: int):
        cfg: CFG = self.sub_cfgs[lab]
        sys.merge_cfg_info(cfg)
        return cfg.start_block.bid, cfg.final_block.bid

    def checkout_cfg(self, lab: int):
        cfg: CFG = sys.analysis_cfgs[lab]
        return cfg

    def generate_flow(self, program_point: ProgramPoint):
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
