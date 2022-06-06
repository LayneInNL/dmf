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
# from __future__ import annotations

# class Singleton:
#     def __init__(self, cls_obj):
#         self.internal: Dict = {}
#         self.cls_obj = cls_obj
#
#     def __repr__(self):
#         return "dict {} cls {}".format(self.internal, self.cls_obj)
#
#     def __le__(self, other: Singleton):
#         return issubset(self.internal, other.internal)
#
#     def __iadd__(self, other: Singleton):
#         update(self.internal, other.internal)
#         return self
#
#     def __contains__(self, field):
#         return field in self.internal
#
#     def __setitem__(self, field, value):
#         self.internal[field] = value
#
#     def __getitem__(self, field):
#         # At first retrieve dict of instance itself.
#         if field in self.internal:
#             return self.internal[field]
#         else:
#             return self.cls_obj.getattr(field)


# class Summary:
#     def __init__(self):
#         self.internal: Dict = {}
#
#     def __le__(self, other: Summary):
#         return issubset_twodict(self.internal, other.internal)
#
#     def __iadd__(self, other: Summary):
#         update_twodict(self.internal, other.internal)
#         return self
