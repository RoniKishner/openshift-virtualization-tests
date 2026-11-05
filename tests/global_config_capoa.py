from typing import Any

import pytest_testconfig
from ocp_resources.datavolume import DataVolume

from utilities.constants.storage import HPP_CAPABILITIES, StorageClassNames
from utilities.storage import HppCsiStorageClass

global config
global_config = pytest_testconfig.load_python(py_file="tests/global_config.py", encoding="utf-8")

storage_class_matrix = [
    {
        StorageClassNames.KUBEVIRT_CSI: {
            "volume_mode": DataVolume.VolumeMode.BLOCK,
            "access_mode": DataVolume.AccessMode.RWX,
            "snapshot": False,
            "online_resize": True,
            "wffc": False,
            "default": True,
            "data_import_cron_source_format": "pvc",
        }
    },
    {HppCsiStorageClass.Name.HOSTPATH_CSI_BASIC: HPP_CAPABILITIES},
    {HppCsiStorageClass.Name.HOSTPATH_CSI_PVC_BLOCK: HPP_CAPABILITIES},
]

storage_class_a = HppCsiStorageClass.Name.HOSTPATH_CSI_BASIC
storage_class_b = StorageClassNames.KUBEVIRT_CSI
default_storage_class = StorageClassNames.KUBEVIRT_CSI
default_volume_mode = DataVolume.VolumeMode.BLOCK
default_access_mode = DataVolume.AccessMode.RWX

for _dir in dir():
    if not config:
        config: dict[str, Any] = {}
    val = locals()[_dir]
    if type(val) not in [bool, list, dict, str]:
        continue

    if _dir in ["encoding", "py_file"]:
        continue

    config[_dir] = locals()[_dir]
