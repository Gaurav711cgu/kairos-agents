"""An available GPU must never be reported as a completed fit or training run."""
from collections import namedtuple
from types import SimpleNamespace
import pytest
from scripts.coding_gpu014 import gpu_rows,inventory


def test_realistic_t4_inventory_is_not_a_fit_claim():
    disk=lambda _:namedtuple('Disk','total used free')(100_000,10_000,90_000)
    result=inventory(run=lambda *_args,**_kw:SimpleNamespace(returncode=0,stdout='Tesla T4, 15360, 15000, 550.54.15\n'),disk=disk)
    assert result['gpus'][0]['total_memory_mib']==15360
    for key in ['training_started','resource_fit_verified','scratch_allocation_admitted','weights_downloaded_by_this_command','dataset_uploaded_by_this_command']:
        assert result[key] is False


def test_missing_nvidia_tool_is_an_explicit_unavailable_measurement():
    def unavailable(*_args,**_kw):raise FileNotFoundError('nvidia-smi')
    result=inventory(run=unavailable)
    assert result['gpus']==[] and result['gpu_inventory_failure_type']=='FileNotFoundError'
    assert not result['training_started']


def test_invalid_gpu_measurements_do_not_become_zero_memory():
    for text in ['', 'T4, N/A, N/A, 550', 'T4, 100, 101, 550', 'T4, 0, 0, 550']:
        with pytest.raises(ValueError):gpu_rows(text)
