# Copyright 2021 LINBIT HA-Solutions GmbH
# See LICENSE file for licensing details.
#
# Learn more about testing at: https://juju.is/docs/sdk/testing

import unittest

from charm import LinstorHighAvailabilityControllerCharm
from ops.testing import Harness


class TestCharm(unittest.TestCase):
    def setUp(self):
        self.harness = Harness(LinstorHighAvailabilityControllerCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.begin()
