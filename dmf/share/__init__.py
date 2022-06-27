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
from typing import Tuple, Set

from dmf.flows import construct_CFG

# simulate modules
modules = {}
# simulate modules for static analysis
analysis_modules = {}
static_import_module = None
# CFG flows
flows = set()
blocks = {}
sub_cfgs = {}
call_return_inter_flows: Set[Tuple[int, int, int, int, int, int, int]] = set()
classdef_inter_flows: Set[Tuple[int, int]] = set()
setter_inter_flows: Set[Tuple[int, int, int]] = set()
getter_inter_flows: Set[Tuple[int, int, int]] = set()
special_init_inter_flows: Set[Tuple[int, int, int]] = set()
dummy_labels: Set[int] = set()
call_labels: Set = set()
return_labels: Set = set()


def create_and_update_cfg(file_path):
    cfg = construct_CFG(file_path)
    update_global_info(cfg)
    return cfg.start_block.bid, cfg.final_block.bid


def update_global_info(cfg):
    flows.update(cfg.flows)
    call_return_inter_flows.update(cfg.call_return_inter_flows)
    classdef_inter_flows.update(cfg.classdef_inter_flows)
    getter_inter_flows.update(cfg.getter_inter_flows)
    setter_inter_flows.update(cfg.setter_inter_flows)
    special_init_inter_flows.update(cfg.special_init_inter_flows)
    blocks.update(cfg.blocks)
    sub_cfgs.update(cfg.sub_cfgs)
    dummy_labels.update(cfg.dummy_labels)
    call_labels.update(cfg.call_labels)
    return_labels.update(cfg.return_labels)
