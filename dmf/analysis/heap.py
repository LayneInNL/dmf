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

from typing import Dict, Set, Tuple

from dmf.analysis.heap_namespace import SizedHeapNamespace


class Heap:
    """
    Heap to store heap allocated objects
    """

    # threshold = 100

    # def threshold_check(self):
    #     if self.singletons is Any:
    #         return
    #     elif len(self.singletons) > self.threshold:
    #         self.singletons = Any
    #     else:
    #         pass

    def __init__(self):
        # self.singletons: Dict[str, SizedHeapNamespace] | Any = {}
        self.singletons: Dict[Tuple, SizedHeapNamespace] = {}

    def __missing__(self, key):
        value = SizedHeapNamespace()
        return value

    def __contains__(self, item):
        return item in self.singletons

    def __getitem__(self, item):
        # if self.singletons is Any:
        #     return Any
        if item not in self.singletons:
            default_value = self.__missing__(item)
            self.singletons[item] = default_value
        # self.threshold_check()
        return self.singletons[item]

    def __le__(self, other: Heap):
        # if self.singletons is Any:
        #     return True
        # elif other.singletons is Any:
        #     return False
        # else:
        for heap_address in self.singletons:
            if heap_address not in other.singletons:
                return False
            else:
                self_namespace: SizedHeapNamespace = self.singletons[heap_address]
                other_namespace: SizedHeapNamespace = other.singletons[heap_address]
                if not self_namespace <= other_namespace:
                    return False
        return True

    def __iadd__(self, other: Heap):
        # if self.singletons is Any:
        #     return self
        # elif other.singletons is Any:
        #     self.singletons = Any
        #     return self
        # else:
        for heap_address in other.singletons:
            if heap_address not in self.singletons:
                self.singletons[heap_address] = other.singletons[heap_address]
            else:
                self_namespace = self.singletons[heap_address]
                other_namespace = other.singletons[heap_address]
                self_namespace += other_namespace
        # self.threshold_check()
        return self

    def __repr__(self):
        return "heaps: {}".format(self.singletons)

    def get_heaper(self) -> Set:
        heaper_set = set()
        for heap_address in self.singletons.keys():
            heaper_set.add(heap_address)
        return heaper_set

    def get_heapee(self) -> Set:
        heapee_set = set()
        pass
