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
import os.path
import sys

from dmf.analysis.analysis import Analysis
from dmf.analysis.state import State
from dmf.analysis.value import ModuleType
from dmf.log.logger import logger
from dmf.share import (
    modules,
    analysis_modules,
    create_and_update_cfg,
)

parser = argparse.ArgumentParser()
parser.add_argument("main", help="the main file path")


def add_builtins_attributes(path):
    main_module = type(sys)("__main__")
    main_module.__file__ = path
    custom_main_module = ModuleType(State())
    # our custom modules, simulating sys.modules
    modules["__main__"] = main_module
    # used in analysis
    analysis_modules["__main__"] = custom_main_module


def add_sys_path(path):
    # our custom root path, simulating sys.path
    # insert being analyzed dir into sys.path
    # for example, dir_name = "C:\\Users\\Layne Liu\\PycharmProjects\\cfg\\dmf\\examples\\"
    dir_name = os.path.dirname(path)
    # insert to the beginning of sys.path
    sys.path.insert(0, dir_name)
    logger.debug("updated sys.path {}".format(sys.path))


if __name__ == "__main__":
    args = parser.parse_args()
    main_file_path = args.main
    abs_path = os.path.abspath(main_file_path)
    logger.debug("Absolute entry file path is: {}".format(abs_path))

    module_name = os.path.basename(abs_path).rpartition(".")[0]
    # add_builtins_attributes(abs_path)
    # add_sys_path(abs_path)

    start_lab, _ = create_and_update_cfg(abs_path)
    analysis = Analysis(start_lab)
    analysis.compute_fixed_point()
