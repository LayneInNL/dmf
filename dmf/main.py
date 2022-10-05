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

if sys.platform == "linux":
    import resource

    resource.setrlimit(resource.RLIMIT_STACK, (2**30, -1))

from dmf.log.logger import logger

# https://docs.python.org/3.7/library/sys.html#sys.setrecursionlimit
sys.setrecursionlimit(10**8)

from dmf.analysis.value import type_2_value
import argparse
import os.path
from dmf.analysis.analysis import Analysis
from dmf.analysis.analysis_types import AnalysisModule

parser = argparse.ArgumentParser()
parser.add_argument("main", help="the main file path")
parser.add_argument("project", help="the project path")


if __name__ == "__main__":
    args = parser.parse_args()
    main_path = args.main
    project_path = args.project
    if not main_path or not project_path:
        exit()

    # project root directory
    project_abs_path = os.path.abspath(project_path)
    sys.analysis_path.append(project_path)
    sys.first_party = os.path.basename(project_abs_path)
    logger.info(f"first party: {sys.first_party}")

    # main file location
    main_abs_file_path = os.path.abspath(main_path)
    cfg = sys.synthesis_cfg(main_abs_file_path)
    entry_label, exit_label = sys.merge_cfg_info(cfg)
    main_module = AnalysisModule(
        tp_name="__main__", tp_package="", tp_code=(entry_label, exit_label)
    )
    sys.analysis_modules["__main__"] = type_2_value(main_module)
    analysis = Analysis()
    analysis.compute_fixed_point()
