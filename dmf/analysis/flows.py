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


def is_call_label(label, call_return_flows):
    for call_label, _ in call_return_flows:
        if label == call_label:
            return True
    return False


def is_entry_point(program_point, inter_flows):
    for call_point, entry_point, exit_point, return_point in inter_flows:
        if program_point == entry_point:
            return True
    return False


def is_exit_point(program_point, inter_flows):
    for call_point, entry_point, exit_point, return_point in inter_flows:
        if program_point == exit_point:
            return True
    return False


def is_return_label(label, call_return_flows):
    for _, return_label in call_return_flows:
        if label == return_label:
            return True
    return False


def get_call_label(label, call_return_flows):
    for call_label, return_label in call_return_flows:
        if label == return_label:
            return call_label


def get_call_point(program_point, inter_flows):
    for call_point, entry_point, exit_point, return_point in inter_flows:
        if program_point == return_point:
            return call_point


def get_return_label(label, call_return_flows):
    for call_label, return_label in call_return_flows:
        if label == call_label:
            return return_label


def get_return_point(program_point, inter_flows):
    for call_point, entry_point, exit_point, return_point in inter_flows:
        if program_point == call_point:
            return return_point
