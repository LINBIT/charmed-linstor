#!/usr/bin/env python3
# Copyright 2021 LINBIT HA-Solutions GmbH
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

"""Charm the service.

Refer to the following post for a quick-start guide that will help you
develop a new k8s charm using the Operator Framework:

    https://discourse.charmhub.io/t/4208
"""

import logging

from oci_image import OCIImageResource, OCIImageResourceError
from ops import charm, framework, main, model

logger = logging.getLogger(__name__)


class LinstorSatelliteCharm(charm.CharmBase):
    _stored = framework.StoredState()

    def __init__(self, *args):
        super().__init__(*args)

        self.linstor_satellite_image = OCIImageResource(self, "linstor-satellite-image")
        self.drbd_injector_image = OCIImageResource(self, "drbd-injector-image")

        self.framework.observe(self.on.install, self._set_pod_spec)
        self.framework.observe(self.on.upgrade_charm, self._set_pod_spec)
        self.framework.observe(self.on.config_changed, self._set_pod_spec)

    def _set_pod_spec(self, event: charm.HookEvent):
        if not self.unit.is_leader():
            return

        try:
            linstor_satellite_image = self.linstor_satellite_image.fetch()
            drbd_injector_image = self.drbd_injector_image.fetch()
        except OCIImageResourceError as e:
            self.model.unit.status = e.status
            event.defer()
            return

        injector_volumes = [
            {
                "name": "device-dir",
                "mountPath": "/dev",
                "hostPath": {"path": "/dev", "type": "Directory"},
            },
            {
                "name": "modules-dir",
                "mountPath": "/lib/modules",
                "hostPath": {"path": "/lib/modules", "type": "Directory"},
            },
        ]
        injector_env = {
            "LB_FAIL_IF_USERMODE_HELPER_NOT_DISABLED": "yes",
            "LB_HOW": "shipped_modules"
        }

        if self.config["compile-module"]:
            injector_env["LB_HOW"] = "compile"
            injector_volumes.append({
                "name": "kernel-src-dir",
                "mountPath": "/usr/src",
                "hostPath": {"path": "/usr/src", "type": "Directory"},
            })

        self.model.unit.status = model.MaintenanceStatus("Setting pod spec")
        self.model.pod.set_spec(
            spec={
                "version": 3,
                "containers": [
                    {
                        "name": "linstor-satellite",
                        "imageDetails": linstor_satellite_image,
                        "args": ["startSatellite"],
                        "ports": [
                            {"name": "linstor-control", "containerPort": self.config["linstor-control-port"]},
                        ],
                        "kubernetes": {"securityContext": {"privileged": True}},
                        "volumeConfig": [
                            {
                                "name": "device-dir",
                                "mountPath": "/dev",
                                "hostPath": {"path": "/dev", "type": "Directory"},
                            },
                            {
                                "name": "sys-dir",
                                "mountPath": "/sys",
                                "hostPath": {"path": "/sys", "type": "Directory"},
                            },
                            {
                                "name": "modules-dir",
                                "mountPath": "/lib/modules",
                                "hostPath": {"path": "/lib/modules", "type": "Directory"},
                            },
                        ],
                    },
                    {
                        "name": "drbd-injector",
                        "init": True,
                        "imageDetails": drbd_injector_image,
                        "kubernetes": {"securityContext": {"privileged": True}},
                        "volumeConfig": injector_volumes,
                        "envConfig": injector_env,
                    },
                ],
                "serviceAccount": {
                    "roles": [
                        {
                            "name": "linstor-satellite",
                            "global": True,
                            "rules": [
                                {
                                    "apiGroups": ["security.openshift.io", "policy"],
                                    "resources": ["securitycontextconstraints", "podsecuritypolicies"],
                                    "resourceNames": ["privileged"],
                                    "verbs": ["use"],
                                },
                            ],
                        },
                    ],
                },
            },
            k8s_resources={
                "kubernetesResources": {
                    "pod": {"hostNetwork": True},
                },
            },
        )

        self.model.unit.status = model.ActiveStatus()


if __name__ == "__main__":
    main.main(LinstorSatelliteCharm)
