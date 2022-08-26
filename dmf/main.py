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

import init

import argparse
import os.path

from dmf.analysis.analysis import Analysis
from dmf.analysis.all_types import AnalysisModule

parser = argparse.ArgumentParser()
parser.add_argument("main", help="the main file path")
parser.add_argument("project", help="the project path")


if __name__ == "__main__":
    args = parser.parse_args()
    main_path = args.main
    project_path = args.project
    if not main_path:
        exit()

    sys.analysis_path.append(project_path)

    # get main module absolute path
    main_abs_file_path = os.path.abspath(main_path)
    project_abs_path = os.path.abspath(project_path)

    # builtin_path = "./resources/builtins.py"
    # abs_builtin_path = os.path.abspath(builtin_path)
    # cfg = sys.synthesis_cfg(abs_builtin_path)
    # entry_label, exit_label = sys.merge_cfg_info(cfg)
    # builtin_module = AnalysisModule(
    #     tp_uuid="builtins", tp_package="", tp_code=(entry_label, exit_label)
    # )
    # sys.analysis_modules["builtins"] = builtin_module
    # analysis = Analysis("builtins")
    # analysis.compute_fixed_point()

    cfg = sys.synthesis_cfg(main_abs_file_path)
    entry_label, exit_label = sys.merge_cfg_info(cfg)
    main_module = AnalysisModule(
        tp_uuid="__main__", tp_package="", tp_code=(entry_label, exit_label)
    )
    sys.analysis_modules["__main__"] = main_module
    analysis = Analysis("__main__")
    analysis.compute_fixed_point()
