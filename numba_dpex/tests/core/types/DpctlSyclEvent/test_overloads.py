import dpctl

from numba_dpex import dpjit


@dpjit
def wait_call(a):
    a.wait()
    return None


def test_wait_DpctlSyclEvent():
    """Test the dpctl.SyclEvent.wait() call overload."""

    e = dpctl.SyclEvent()
    wait_call(e)
