# Copyright 2021 LINBIT HA-Solutions GmbH
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing

import unittest

from charm import LinstorSatelliteCharm, _parse_storage_pool_config, StoragePoolConfig
from ops.model import ActiveStatus
from ops.testing import Harness


class TestCharm(unittest.TestCase):
    def setUp(self):
        self.harness = Harness(LinstorSatelliteCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.add_oci_resource("linstor-satellite-image")
        self.harness.add_oci_resource("drbd-injector-image")
        self.harness.begin_with_initial_hooks()

    def test_is_ready(self):
        self.assertEqual(self.harness.model.unit.status, ActiveStatus())


class TestCharmHelpers(unittest.TestCase):
    def test_parse_storage_pool_config(self):
        testcases = [
            {
                "conf": "",
                "expected": [],
            },
            {
                "conf": "provider=lvmthin,provider_name=storage/thinpool,name=thinpool",
                "expected": [StoragePoolConfig("thinpool", "lvmthin", "storage/thinpool", [])],
            },
            {
                "conf": "provider=lvmthin,provider_name=storage/thinpool,name=thinpool "
                        "provider=zfs,provider_name=ssds,name=ssds,devices=/dev/sdc,devices=/dev/sdd",
                "expected": [
                    StoragePoolConfig("thinpool", "lvmthin", "storage/thinpool", []),
                    StoragePoolConfig("ssds", "zfs", "ssds", ["/dev/sdc", "/dev/sdd"]),
                ],
            },
        ]

        for test in testcases:
            with self.subTest(conf=test["conf"]):
                actual = _parse_storage_pool_config(test["conf"])
                self.assertEqual(test["expected"], actual)
