import pytest

from ocp_resources.cdi import CDI
from ocp_resources.data_import_cron import DataImportCron
from ocp_resources.hyperconverged import HyperConverged
from ocp_resources.resource import ResourceEditor
from ocp_resources.ssp import SSP
from ocp_resources.virtual_machine_cluster_instancetype import (
    VirtualMachineClusterInstancetype,
)
from ocp_resources.virtual_machine_cluster_preference import (
    VirtualMachineClusterPreference,
)
from utilities.artifactory import get_test_artifact_server_url, get_artifactory_secret, get_artifactory_config_map, \
    cleanup_artifactory_secret_and_config_map, get_artifactory_image_pull_secret

from utilities.constants import Images
from utilities.hco import ResourceEditorValidateHCOReconcile
from utilities.virt import VirtualMachineForTests


def get_mismatched_fields_list(
    vm_instancetype_dict,
    vm_reference_dict,
    instancetype_object_dict,
    preference_object_dict,
):
    mismatch_list = []
    if vm_instancetype_dict["name"] != instancetype_object_dict["metadata"]["name"]:
        mismatch_list.append(
            f"expected vm instancetype name to be: {instancetype_object_dict['metadata']['name']} "
            f"got {vm_instancetype_dict['name']}"
        )
    if vm_instancetype_dict["kind"] != instancetype_object_dict["kind"]:
        mismatch_list.append(
            f"expected vm instancetype kind to be: {vm_instancetype_dict['kind']} "
            f"got {instancetype_object_dict['kind']}"
        )
    if vm_reference_dict["name"] != preference_object_dict["metadata"]["name"]:
        mismatch_list.append(
            f"expected vm preference name to be: {instancetype_object_dict['metadata']['name']} "
            f"got {vm_instancetype_dict['name']}"
        )
    if vm_reference_dict["kind"] != preference_object_dict["kind"]:
        mismatch_list.append(
            f"expected vm preference kind to be: {vm_instancetype_dict['kind']} got {instancetype_object_dict['kind']}"
        )
    return mismatch_list


@pytest.fixture()
def vm_cluster_instance_type_to_update(unprivileged_client):
    cluster_instancetype_list = list(
        VirtualMachineClusterInstancetype.get(
            client=unprivileged_client,
            label_selector="instancetype.kubevirt.io/memory=4Gi, instancetype.kubevirt.io/cpu=1",
        )
    )
    assert cluster_instancetype_list, "No cluster instance type found on the cluster"
    return cluster_instancetype_list[0]


@pytest.fixture()
def rhel_9_vm_cluster_preference(unprivileged_client):
    return VirtualMachineClusterPreference(client=unprivileged_client, name="rhel.9")


@pytest.fixture()
def simple_rhel_vm(admin_client, namespace):
    with VirtualMachineForTests(
        client=admin_client,
        name="rhel-vm-with-instance-type",
        namespace=namespace.name,
        image=Images.Rhel.RHEL9_REGISTRY_GUEST_IMG,
    ) as vm:
        yield vm


@pytest.fixture()
def updated_vm_with_instancetype_and_preference(
    simple_rhel_vm, vm_cluster_instance_type_to_update, rhel_9_vm_cluster_preference
):
    spec_dict = {
        "instancetype": {
            "kind": vm_cluster_instance_type_to_update.kind,
            "name": vm_cluster_instance_type_to_update.name,
        },
        "preference": {
            "kind": rhel_9_vm_cluster_preference.kind,
            "name": rhel_9_vm_cluster_preference.name,
        },
        "template": {"spec": {"domain": {"resources": None}}},
    }
    ResourceEditor(patches={simple_rhel_vm: {"spec": spec_dict}}).update()
    return simple_rhel_vm


@pytest.mark.gating
@pytest.mark.polarion("CNV-9680")
def test_add_reference_to_existing_vm(
    updated_vm_with_instancetype_and_preference,
    vm_cluster_instance_type_to_update,
    rhel_9_vm_cluster_preference,
):
    vm_spec = updated_vm_with_instancetype_and_preference.instance.spec
    vm_instancetype_dict = vm_spec["instancetype"]
    vm_preference_dict = vm_spec["preference"]
    mismatch_list = get_mismatched_fields_list(
        vm_instancetype_dict=vm_instancetype_dict,
        vm_reference_dict=vm_preference_dict,
        instancetype_object_dict=vm_cluster_instance_type_to_update.instance.to_dict(),
        preference_object_dict=rhel_9_vm_cluster_preference.instance.to_dict(),
    )
    assert not mismatch_list, f"Some references were not updated in the VM: {mismatch_list}"


def test_roni(admin_client, golden_images_namespace):
    from ocp_resources.resource import ResourceEditor, get_client
    from ocp_resources.service_account import ServiceAccount

    default_sa = ServiceAccount(name="default", namespace=golden_images_namespace.name, client=get_client())
    existing_secrets = default_sa.instance.get("imagePullSecrets", [])
    existing_secret_names = {secret_ref.get("name") for secret_ref in existing_secrets}

    if "cnv-tests-artifactory-secret-image-pull" not in existing_secret_names:
        all_secrets = existing_secrets + [{"name": "cnv-tests-artifactory-secret-image-pull"}]
        ResourceEditor(patches={default_sa: {"imagePullSecrets": all_secrets}}).update()

    win2k22_template = {
        "metadata": {
            "annotations": {
                "cdi.kubevirt.io/storage.bind.immediate.requested": "true",
            },
            "labels": {"kubevirt.io/dynamic-credentials-support": "true"},
            "name": "win2k22-image-cron",
        },
        "spec": {
            "managedDataSource": "win2k22",
            "schedule": "34 1/12 * * *",
            "template": {
                "metadata": {},
                "spec": {
                    "source": {
                        "registry": {
                            "pullMethod": "node",
                            "url": f"{get_test_artifact_server_url(schema='registry')}/{Images.Windows.DOCKER_IMAGE_DIR}/windows2k22-container-disk:4.99",
                            "certConfigMap": "artifactory-configmap",
                            "secretRef": "cnv-tests-artifactory-secret",
                        }
                    },
                    "storage": {"resources": {"requests": {"storage": Images.Windows.CONTAINER_DISK_DV_SIZE}}},
                },
            },
        },
    }

    # If you need to append to existing templates, get them first:
    hco = HyperConverged(name="kubevirt-hyperconverged", namespace="openshift-cnv")
    existing_templates = hco.instance.spec.get("dataImportCronTemplates", [])
    all_templates = existing_templates + [win2k22_template]

    with ResourceEditorValidateHCOReconcile(
        patches={hco: {"spec": {"dataImportCronTemplates": all_templates}}},
        list_resource_reconcile=[SSP, CDI],
    ):
        breakpoint()
        artifactory_secret = get_artifactory_secret(namespace=golden_images_namespace.name)
        artifactory_config_map = get_artifactory_config_map(namespace=golden_images_namespace.name)
        image_pull_secret = get_artifactory_image_pull_secret(namespace=golden_images_namespace.name)
        win_2k22_dic = DataImportCron(name="win2k22-image-cron", namespace=golden_images_namespace.name, client=admin_client)
        win_2k22_dic.clean_up()
        breakpoint()
        assert True

    cleanup_artifactory_secret_and_config_map(
        artifactory_secret=artifactory_secret, artifactory_config_map=artifactory_config_map
    )
    image_pull_secret.clean_up()
