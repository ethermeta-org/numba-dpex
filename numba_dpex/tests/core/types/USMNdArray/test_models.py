# SPDX-FileCopyrightText: 2023 Intel Corporation
#
# SPDX-License-Identifier: Apache-2.0

from numba.core.registry import cpu_target

from numba_dpex.core.descriptor import dpex_kernel_target
from numba_dpex.core.types.usm_ndarray_type import USMNdArray


def test_flattened_member_count():
    """Test that the number of flattened member count matches the number of
    flattened args generated by the CpuTarget's ArgPacker.
    """

    cputargetctx = cpu_target.target_context
    kerneltargetctx = dpex_kernel_target.target_context
    dpex_dmm = kerneltargetctx.data_model_manager

    for ndim in range(4):
        dty = USMNdArray(ndim)
        argty_tuple = tuple([dty])
        datamodel = dpex_dmm.lookup(dty)
        num_flattened_args = datamodel.flattened_field_count
        ap = cputargetctx.get_arg_packer(argty_tuple)

        assert num_flattened_args == len(ap._be_args)
