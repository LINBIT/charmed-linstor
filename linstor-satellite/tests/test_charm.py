# Copyright 2021 LINBIT HA-Solutions GmbH
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing

import unittest

from charm import _parse_storage_pool_config, StoragePoolConfig


class TestCharmHelpers(unittest.TestCase):
    def test_parse_storage_pool_config(self):
        testcases = [
            {
                "conf": "",
                "expected": [],
            },
            {
                "conf": "provider=lvmthin,provider_name=storage/thinpool,name=thinpool",
                "expected": [
                    StoragePoolConfig("thinpool", "lvmthin", "storage/thinpool", [])
                ],
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
