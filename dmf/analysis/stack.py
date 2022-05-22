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

from collections import defaultdict
from typing import List

import dmf.share
from dmf.analysis.value import ValueDict, Value


class Frame:
    def __init__(self, f_locals=None, f_back=None, f_globals=None):
        self.f_locals: ValueDict[str, Value] = f_locals
        self.f_back: Frame | None = f_back
        self.f_globals: ValueDict[str, Value] = f_globals

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
        return self

    def __repr__(self):
        res = "local: {}, back: {}, global: {}".format(
            self.f_locals, self.f_back, self.f_globals
        )
        return res

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

        raise AttributeError(var)

    def write_var(self, var: str, value: Value):
        self.f_locals[var] = value

    def write_var_to_global(self, var: str, value: Value):
        self.f_globals[var] = value


class Stack:
    def __init__(self, stack: Stack = None):
        self.frames: List[Frame] = []
        if stack is not None:
            ns_mark = self.duplicate_frames(stack)
            self.fill_frames(stack, ns_mark)

    def duplicate_frames(self, stack: Stack):
        frames = self.frames
        f_back = None
        for f in stack.frames:
            f.is_module = f.f_globals is f.f_locals
            frame = Frame()
            frame.f_back = f_back
            f_back = frame
            frames.append(frame)

        ns_mark = defaultdict(list)
        for idx, f in enumerate(stack.frames):
            if f.f_locals is not None:
                ns_mark[id(f.f_locals)].append((idx, "f_locals"))
            if f.f_globals is not None:
                ns_mark[id(f.f_globals)].append((idx, "f_globals"))

        return ns_mark

    def fill_frames(self, stack: Stack, ns_mark: defaultdict):
        for _, nss in ns_mark.items():
            first_ns_loc = nss[0]
            old_frame = stack.frames[first_ns_loc[0]]
            attr = first_ns_loc[1]
            old_ns = getattr(old_frame, attr)
            new_ns = old_ns.copy()
            for ns in nss:
                setattr(self.frames[ns[0]], ns[1], new_ns)
        for frame in self.frames:
            glo = frame.f_globals
            dmf.share.analysis_modules[glo["__name__"]].namespace = glo

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
        )
        self.push_frame(new_frame)
