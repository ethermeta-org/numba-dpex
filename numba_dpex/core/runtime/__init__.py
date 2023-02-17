# Copyright 2021 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import llvmlite.binding as ll

from ._dpexrt_python import c_helpers

# Register the helper function in _dpexrt_python so that we can insert
# calls to them via llvmlite.
for (
    py_name,
    c_address,
) in c_helpers.items():
    ll.add_symbol(py_name, c_address)