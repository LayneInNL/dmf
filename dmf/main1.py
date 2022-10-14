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
import timeit

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


def with_temps(crude, refined):
    total: int = 0
    difference: int = 0

    all_program_points = set(crude.keys()) | set(refined.keys())

    for program_point in all_program_points:
        if program_point in crude and program_point not in refined:
            crude_ns = crude[program_point].stack.get_curr_namespace()
            crude_ns_locals = crude_ns.extract_locals()
            total += len(crude_ns_locals)
            difference += len(crude_ns_locals)
            continue
        elif program_point not in crude and program_point in refined:
            refined_ns = refined[program_point].stack.get_curr_namespace()
            refined_ns_locals = refined_ns.extract_locals()
            total += len(refined_ns_locals)
            difference += len(refined_ns_locals)
            continue
        else:
            crude_ns = crude[program_point].stack.get_curr_namespace()
            crude_ns_locals = crude_ns.extract_locals()
            refined_ns = refined[program_point].stack.get_curr_namespace()
            refined_ns_locals = refined_ns.extract_locals()
            local_names = set(crude_ns_locals.keys()) | set(refined_ns_locals.keys())
            for name in local_names:
                if name in crude_ns_locals and name not in refined_ns_locals:
                    raise NotImplementedError
                elif name not in crude_ns_locals and name in refined_ns_locals:
                    raise NotImplementedError
                else:
                    crude_value = crude_ns_locals[name]
                    refined_value = refined_ns_locals[name]
                    if not (crude_value <= refined_value <= crude_value):
                        difference += 1
                    total += 1
    logger.critical("with temps: {} {}".format(difference, total))


def without_temps(crude, refined):
    total: int = 0
    difference: int = 0
    all_program_points = set(crude.keys()) | set(refined.keys())
    for program_point in all_program_points:
        if program_point in crude and program_point not in refined:
            crude_ns = crude[program_point].stack.get_curr_namespace()
            crude_ns_locals = crude_ns.extract_local_nontemps()
            total += len(crude_ns_locals)
            difference += len(crude_ns_locals)
            continue
        elif program_point not in crude and program_point in refined:
            refined_ns = refined[program_point].stack.get_curr_namespace()
            refined_ns_locals = refined_ns.extract_local_nontemps()
            total += len(refined_ns_locals)
            difference += len(refined_ns_locals)
            continue
        else:
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
                    crude_value = crude_ns_locals[name]
                    refined_value = refined_ns_locals[name]
                    if not (crude_value <= refined_value <= crude_value):
                        difference += 1
                    total += 1
    logger.critical("without temps: {} {}".format(difference, total))


if __name__ == "__main__":
    start = timeit.default_timer()
    sys.open_graph = False
    sys.depth = 1

    main_dir = "/home/layne/Desktop/example_projects/eulerlib"
    project_path = main_dir
    # project root directory
    project_abs_path = os.path.abspath(project_path)
    sys.analysis_path.append(project_path)
    sys.first_party = os.path.basename(project_abs_path)
    logger.info(f"first party: {sys.first_party}")

    pyfiles = [f for f in os.listdir(main_dir) if os.path.isfile(f)]
    sum_time_diff1 = 0
    sum_time_diff2 = 0
    for f in pyfiles:
        main_path = f
        # main file location
        main_abs_file_path = os.path.abspath(main_path)

        # crude semantics
        sys.analysis_type = "crude"
        analysis1 = Analysis(main_abs_file_path)
        analysis1.compute_fixed_point()
        crude = analysis1.analysis_effect_list
        del crude[2, ()]
        end = timeit.default_timer()
        time_diff = end - start
        sum_time_diff1 += time_diff

        start2 = timeit.default_timer()
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
        sys.analysis_type = "refined"
        analysis2 = Analysis(main_abs_file_path)
        analysis2.compute_fixed_point()
        refined = analysis2.analysis_effect_list
        del refined[2, ()]
        end2 = timeit.default_timer()
        time_diff2 = end2 - start2
        sum_time_diff2 += time_diff2

        with_temps(crude, refined)
        without_temps(crude, refined)
        logger.critical(f"crude analysis {time_diff}")
        logger.critical(f"refine analysis {time_diff2}")
