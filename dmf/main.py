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
from dmf.log.logger import logger

if sys.platform == "linux":
    import resource

    resource.setrlimit(resource.RLIMIT_STACK, (2**30, -1))
# https://docs.python.org/3.7/library/sys.html#sys.setrecursionlimit
sys.setrecursionlimit(10**8)

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

    # crude semantics
    analysis = Analysis(main_abs_file_path)
    analysis.compute_fixed_point()
    crude = analysis.analysis_effect_list

    # re-init these attributes
    # mimic sys.modules, as fake ones
    sys.analysis_modules = {}
    # mimic sys.modules, but used for typeshed
    sys.analysis_typeshed_modules = {}
    # mimic sys.modules
    sys.fake_analysis_modules = {}

    # mimic exec(module)
    sys.prepend_flows = []

    # path-sensitive semantics
    analysis = Analysis(main_abs_file_path)
    analysis.compute_fixed_point()
    refined = analysis.analysis_effect_list

    total: int = 0
    difference: int = 0
    for program_point in refined:
        crude_ns = crude[program_point].stack.get_curr_namespace()
        crude_ns_locals = crude_ns.extract_local_nontemps()
        refined_ns = refined[program_point].stack.get_curr_namespace()
        refined_ns_locals = refined_ns.extract_local_nontemps()
        local_names = set(crude_ns_locals.keys()) | set(refined_ns_locals.keys())

        for name in local_names:
            if name in crude_ns_locals and name not in refined_ns_locals:
                raise NotImplementedError
            elif name not in crude_ns_locals and name in refined_ns_locals:
                raise NotImplementedError
            else:
                print(name)
                crude_value = crude_ns_locals[name]
                refined_value = refined_ns_locals[name]
                if not (crude_value <= refined_value <= crude_value):
                    difference += 1
                total += 1

    logger.critical(f"{difference}, {total}")
