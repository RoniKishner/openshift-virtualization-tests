@@ -3,7 +3,7 @@
 from tests.infrastructure.instance_types.supported_os.constants import (
     TEST_CREATE_VM_TEST_NAME,
     TEST_START_VM_TEST_NAME,
-    TESTS_MIGRATE_VM,
+    TESTS_MIGRATE_VM, TESTS_MODULE_IDENTIFIER,
 )
 from tests.infrastructure.instance_types.utils import (
     assert_kernel_lockdown_mode,
@@ -27,8 +27,6 @@
 
 pytestmark = [pytest.mark.post_upgrade]
 
-TESTS_MODULE_IDENTIFIER = "TestCommonInstancetypeRhel"
-
 
 @pytest.mark.arm64
 @pytest.mark.s390x