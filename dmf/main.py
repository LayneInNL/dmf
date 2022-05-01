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

import argparse
import logging
import os.path

from dmf.analysis.lattice import Lattice
from dmf.analysis.stack import create_first_frame
from dmf.analysis.state import State
from dmf.analysis.analysis import Analysis
from dmf.analysis.manager import ModuleManager
from dmf.analysis.object_types.module import Module
from dmf.py2flows.py2flows.main import construct_CFG

logging.basicConfig(level=logging.DEBUG)
parser = argparse.ArgumentParser()
parser.add_argument("file_path", help="the file path")

if __name__ == "__main__":
    args = parser.parse_args()
    abs_path = os.path.abspath(args.file_path)
    logging.debug("Entry file is: {}".format(abs_path))

    first_module = Module(abs_path)
    first_module.name = __name__

    module_manager = ModuleManager()
    module_manager[abs_path] = first_module

    state = State()
    initial_frame = create_first_frame()
    state.push_frame_to_stack(initial_frame)
    lattice = Lattice()
    lattice[()] = state

    cfg = construct_CFG(abs_path)
    mfp = Analysis(cfg, lattice)
    mfp.compute_fixed_point()
