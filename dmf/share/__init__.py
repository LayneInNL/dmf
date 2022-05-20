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

from dmf.flows import construct_CFG

modules = {}
analysis_modules = {}
flows = set()
call_return_flows = set()
blocks = {}
sub_cfgs = {}

static_import_module = None


def create_and_update_cfg(file_path):
    cfg = construct_CFG(file_path)
    flows.update(cfg.flows)
    call_return_flows.update(cfg.call_return_flows)
    blocks.update(cfg.blocks)
    sub_cfgs.update(cfg.sub_cfgs)
    return cfg.start_block.bid, cfg.final_block.bid


# static_builtins simulate builtins
static_builtins = None
