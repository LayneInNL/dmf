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
from __future__ import annotations

from typing import Dict, List

from dmf.analysis.value import ValueDict, Value


class Frame:
    def __init__(self, f_locals=None, f_back=None, f_globals=None, f_builtins=None):
        self.f_locals: ValueDict[str, Value] = f_locals
        self.f_back: Frame | None = None if f_back is None else ValueDict()
        self.f_globals: ValueDict[str, Value] = f_globals
        self.f_builtins: ValueDict[str, Value] = (
            ValueDict() if f_builtins is None else f_builtins
        )
        self.is_module = None

    def __contains__(self, var):
        return var in self.f_locals

    # compare f_locals, f_globals and f_builtins
    # don't know how to compare f_back for now
    def __le__(self, other: Frame):
        res = self.f_locals <= other.f_locals and self.f_globals <= other.f_globals
        return res

    def __iadd__(self, other: Frame):
        self.f_locals += other.f_locals
        self.f_globals += other.f_globals
        self.f_builtins += other.f_builtins
        return self

    def __repr__(self):
        return self.f_locals.__repr__()

    def read_var(self, var):
        # Implement LEGB rule
        if var in self.f_locals:
            return self.f_locals[var]

        parent_frame: Frame = self.f_back
        while parent_frame is not None and parent_frame.f_globals is self.f_globals:
            if var in parent_frame.f_locals:
                return parent_frame.f_locals[var]
            else:
                parent_frame = parent_frame.f_back

        if var in self.f_globals:
            return self.f_globals[var]

        if var in self.f_builtins:
            return self.f_builtins[var]

        raise AttributeError(var)

    def write_var(self, var: str, value: Value):
        self.f_locals[var] = value

    def write_var_to_global(self, var: str, value: Value):
        self.f_globals[var] = value


class Stack:
    def __init__(self, stack: Stack = None):
        self.frames: List[Frame] = []
        if stack is not None:
            self.duplicate_frames(stack)
            self.fill_frames(stack)

    def duplicate_frames(self, stack: Stack):
        frames = self.frames
        f_back = None
        for f in stack.frames:
            f.is_module = f.f_globals is f.f_locals
            frame = Frame()
            frame.f_back = f_back
            f_back = frame
            frames.append(frame)

    def fill_frames(self, stack: Stack):
        start_loc = 0
        end_loc = 0
        while end_loc < len(stack.frames):
            while (
                end_loc < len(stack.frames)
                # check globals
                and stack.frames[start_loc].f_globals is stack.frames[end_loc].f_globals
            ):
                end_loc += 1
            # update global ns
            f_globals_copy = stack.frames[start_loc].f_globals.copy()
            for index in range(start_loc, end_loc):
                curr_frame = self.frames[index]
                curr_frame.f_globals = f_globals_copy
                # update module
                if stack.frames[index].is_module:
                    curr_frame.f_locals = f_globals_copy
                else:
                    curr_frame.f_locals = stack.frames[index].f_locals.copy()
            start_loc = end_loc

    def __le__(self, other: Stack):
        frame_pairs = zip(reversed(self.frames), reversed(other.frames))
        for frame_pair in frame_pairs:
            if not frame_pair[0] <= frame_pair[1]:
                return False
        return True

    def __iadd__(self, other: Stack):
        frame_pairs = zip(reversed(self.frames), reversed(other.frames))
        for frame_pair1, frame_pair2 in frame_pairs:
            frame_pair1 += frame_pair2
        return self

    def __repr__(self):
        return self.frames.__repr__()

    def push_frame(self, frame: Frame):
        self.frames.append(frame)

    def pop_frame(self):
        self.frames = self.frames[:-1]

    def top_frame(self) -> Frame:
        return self.frames[-1]

    def read_var(self, var):
        return self.top_frame().read_var(var)

    def write_var(self, var, value):
        return self.top_frame().write_var(var, value)

    def copy(self):
        copied = Stack(self)
        return copied

    def next_ns(self):
        curr_frame = self.top_frame()
        new_frame = Frame(
            f_locals=ValueDict(),
            f_back=curr_frame,
            f_globals=curr_frame.f_globals,
            f_builtins=curr_frame.f_builtins,
        )
        self.push_frame(new_frame)
