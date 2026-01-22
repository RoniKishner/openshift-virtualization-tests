import pytest
from ocp_resources.validating_admission_policy import ValidatingAdmissionPolicy
from ocp_resources.validating_admission_policy_binding import ValidatingAdmissionPolicyBinding
from ocp_resources.virtual_machine_cluster_instancetype import (
    VirtualMachineClusterInstancetype,
)

from tests.infrastructure.instance_types.utils import assert_mismatch_vendor_label
from utilities.constants import VIRT_OPERATOR, Images
from utilities.virt import VirtualMachineForTests, running_vm


@pytest.fixture()
def deployed_validating_admission_policy(admin_client):
    with ValidatingAdmissionPolicy(
        client=admin_client,
        name="windows-vcpu-overcommit",
        failure_policy="Fail",
        match_conditions=[
            {
                "expression": (
                    "(('kubevirt.io/preference-name' in object.metadata.annotations) && "
                    "(object.metadata.annotations['kubevirt.io/preference-name'].lowerAscii().contains('windows'))) || "
                    "(('kubevirt.io/cluster-preference-name' in object.metadata.annotations) && "
                    "(object.metadata.annotations['kubevirt.io/cluster-preference-name']"
                    ".lowerAscii().contains('windows'))) || "
                    "(('vm.kubevirt.io/os' in object.metadata.annotations) && "
                    "(object.metadata.annotations['vm.kubevirt.io/os'].lowerAscii().contains('windows')))"
                ),
                "name": "windows-vcpu-overcommit",
            }
        ],
        match_constraints={
            "resourceRules": [
                {
                    "apiGroups": ["kubevirt.io"],
                    "apiVersions": ["*"],
                    "operations": ["CREATE", "UPDATE"],
                    "resources": ["virtualmachineinstances"],
                }
            ]
        },
        validations=[
            {
                "expression": (
                    "has(object.spec.domain.cpu.dedicatedCpuPlacement) && "
                    "object.spec.domain.cpu.dedicatedCpuPlacement == true"
                ),
                "message": (
                    "Windows VMIs require dedicated CPU placement. Set spec.domain.cpu.dedicatedCpuPlacement to true."
                ),
            }
        ],
    ) as vap:
        with ValidatingAdmissionPolicyBinding(
            client=admin_client,
            name="windows-vcpu-overcommit-binding",
            policy_name="windows-vcpu-overcommit",
            validation_actions=["Deny"],
        ):
            yield vap


@pytest.mark.sno
@pytest.mark.post_upgrade
@pytest.mark.gating
@pytest.mark.conformance
@pytest.mark.polarion("CNV-10358")
def test_common_instancetype_vendor_labels(base_vm_cluster_instancetypes):
    assert_mismatch_vendor_label(resources_list=base_vm_cluster_instancetypes)


@pytest.mark.hugepages
@pytest.mark.special_infra
@pytest.mark.tier3
@pytest.mark.polarion("CNV-10387")
def test_cx1_instancetype_profile(unprivileged_client, namespace):
    with VirtualMachineForTests(
        client=unprivileged_client,
        name="rhel-vm-with-cx1",
        namespace=namespace.name,
        image=Images.Rhel.RHEL9_REGISTRY_GUEST_IMG,
        vm_instance_type=VirtualMachineClusterInstancetype(client=unprivileged_client, name="cx1.medium1gi"),
    ) as vm:
        running_vm(vm=vm, wait_for_interfaces=False, check_ssh_connectivity=False)


@pytest.mark.post_upgrade
@pytest.mark.polarion("CNV-11288")
def test_common_instancetype_owner(base_vm_cluster_instancetypes):
    failed_ins_type = []
    for vm_cluster_instancetype in base_vm_cluster_instancetypes:
        if (
            vm_cluster_instancetype.labels[f"{vm_cluster_instancetype.ApiGroup.APP_KUBERNETES_IO}/managed-by"]
            != VIRT_OPERATOR
        ):
            failed_ins_type.append(vm_cluster_instancetype.name)
    assert not failed_ins_type, f"The following instance types do no have {VIRT_OPERATOR} owner: {failed_ins_type}"


@pytest.mark.polarion("CNV-0")
def test_d1_instancetype_profile(unprivileged_client, namespace, deployed_validating_admission_policy):
    with VirtualMachineForTests(
        client=unprivileged_client,
        name="rhel-vm-with-d1",
        namespace=namespace.name,
        image=Images.Rhel.RHEL9_REGISTRY_GUEST_IMG,
        vm_instance_type=VirtualMachineClusterInstancetype(client=unprivileged_client, name="d1.large"),
    ) as vm:
        running_vm(vm=vm, wait_for_interfaces=False, check_ssh_connectivity=False)
