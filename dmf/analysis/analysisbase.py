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
from typing import Set, Tuple, Dict

import dmf.share
from dmf.flows import CFG
from dmf.flows.flows import BasicBlock
from dmf.log.logger import logger

ProgramPoint = Tuple[int, Tuple]


class AnalysisBase:
    def __init__(self):
        self.flows: Set[Tuple[int, int]] = dmf.share.flows

        self.dummy_labels = dmf.share.dummy_labels
        self.call_labels = dmf.share.call_labels
        self.return_labels = dmf.share.return_labels
        self.call_return_inter_flows = dmf.share.call_return_inter_flows
        self.classdef_inter_flows = dmf.share.classdef_inter_flows
        self.setter_inter_flows = dmf.share.setter_inter_flows
        self.getter_inter_flows = dmf.share.getter_inter_flows
        self.special_init_flows = dmf.share.special_init_inter_flows

        self.blocks: Dict[int, BasicBlock] = dmf.share.blocks
        self.sub_cfgs: Dict[int, CFG] = dmf.share.sub_cfgs
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
        logger.info(f"{label} not in call_return_inter_flows")
        for call_label, return_label, dummy_return_label in self.getter_inter_flows:
            if label == call_label:
                return return_label, dummy_return_label
        logger.info(f"{label} not in getter_inter_flows")
        for call_label, return_label, dummy_return_label in self.setter_inter_flows:
            if label == call_label:
                return return_label, dummy_return_label
        logger.info(f"{label} not in setter_inter_flows")
        raise KeyError

    def get_init_return_label(self, label):
        for l1, l2, l3 in self.special_init_flows:
            if label == l1:
                return l2, l3
        raise KeyError

    def add_sub_cfg(self, lab: int):
        cfg: CFG = self.sub_cfgs[lab]
        dmf.share.update_global_info(cfg)
        return cfg, cfg.start_block.bid, cfg.final_block.bid

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
