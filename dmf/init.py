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

# https://docs.python.org/3.7/library/sys.html#sys.setrecursionlimit
# sys.setrecursionlimit(10000)

from dmf.flows import construct_CFG

# stack of state
sys.stack = None
# heap of state
sys.heap = None
# program_point
sys.program_point = None

# mimic sys.path
sys.analysis_path = []
# mimic sys.meta_path
sys.analysis_meta_path = []
# mimic sys.path_hooks
sys.analysis_path_hooks = []
# mimic sys.modules, as fake ones
sys.analysis_modules = {}
# mimic sys.modules, but used for typeshed
sys.analysis_typeshed_modules = {}
# mimic sys.modules
sys.fake_analysis_modules = {}
# mimic flows
sys.analysis_flows = set()
# mimic blocks
sys.analysis_blocks = {}
# mimic cfgs
sys.analysis_cfgs = {}
# mimic special flows
sys.call_flow_tuples = set()
sys.classdef_flow_tuples = set()
sys.magic_right_inter_tuples = set()
sys.magic_left_inter_tuples = set()
sys.magic_del_inter_tuples = set()
sys.special_init_inter_flows = set()
# mimic labels
sys.dummy_labels = set()
sys.call_labels = set()
sys.return_labels = set()


def merge_cfg_info(cfg):
    sys.analysis_flows.update(cfg.flows)
    sys.analysis_blocks.update(cfg.blocks)
    sys.analysis_cfgs.update(cfg.sub_cfgs)

    sys.call_flow_tuples.update(cfg.call_return_inter_flows)
    sys.classdef_flow_tuples.update(cfg.classdef_inter_flows)
    sys.magic_right_inter_tuples.update(cfg.magic_right_inter_flows)
    sys.magic_left_inter_tuples.update(cfg.magic_left_inter_flows)
    sys.magic_del_inter_tuples.update(cfg.magic_del_inter_flows)
    sys.special_init_inter_flows.update(cfg.special_init_inter_flows)

    sys.dummy_labels.update(cfg.dummy_labels)
    sys.call_labels.update(cfg.call_labels)
    sys.return_labels.update(cfg.return_labels)

    return cfg.start_block.bid, cfg.final_block.bid


sys.merge_cfg_info = merge_cfg_info

# use global variables to store all cfg information
def synthesis_cfg(file_path):
    cfg = construct_CFG(file_path)
    return cfg


sys.synthesis_cfg = synthesis_cfg


def print_status():
    print("Start to analyze")
