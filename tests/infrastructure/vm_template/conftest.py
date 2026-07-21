import pytest
from ocp_resources.virtual_machine_cluster_instancetype import VirtualMachineClusterInstancetype
from ocp_resources.virtual_machine_cluster_preference import VirtualMachineClusterPreference
from ocp_resources.virtual_machine_template import VirtualMachineTemplate

from utilities.constants.images import OS_FLAVOR_FEDORA
from utilities.constants.instance_types import U1_SMALL


@pytest.fixture()
def valid_vm_template(unprivileged_client, namespace):
    with VirtualMachineTemplate(
        client=unprivileged_client,
        name="valid-test-template",
        namespace=namespace.name,
        parameters=[
            {
                "name": "NAME",
                "generate": "expression",
                "from": "vm-[a-z0-9]{8}",
                "description": "Unique VM name",
            },
            {
                "name": "INSTANCETYPE",
                "value": U1_SMALL,
                "description": "Instance type for the VM",
            },
            {
                "name": "PREFERENCE",
                "value": OS_FLAVOR_FEDORA,
                "description": "VM preference",
            },
        ],
        virtual_machine={
            "metadata": {"name": "${NAME}"},
            "spec": {
                "instancetype": {
                    "kind": VirtualMachineClusterInstancetype.kind,
                    "name": "${INSTANCETYPE}",
                },
                "preference": {
                    "kind": VirtualMachineClusterPreference.kind,
                    "name": "${PREFERENCE}",
                },
                "dataVolumeTemplates": [
                    {
                        "metadata": {"name": "${NAME}"},
                        "spec": {
                            "sourceRef": {
                                "kind": "DataSource",
                                "name": "rhel10",
                                "namespace": "openshift-virtualization-os-images",
                            },
                            "storage": {
                                "resources": {
                                    "requests": {
                                        "storage": "30Gi",
                                    }
                                }
                            },
                        },
                    }
                ],
                "template": {
                    "spec": {
                        "architecture": "amd64",
                        "domain": {
                            "devices": {
                                "autoattachPodInterface": False,
                            }
                        },
                    }
                },
            },
        },
    ) as vm_template:
        yield vm_template
