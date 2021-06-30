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

__version__ = "1.0.0-alpha0"


class LinstorCSIControllerCharm(charm.CharmBase):
    _stored = framework.StoredState()

    def __init__(self, *args):
        super().__init__(*args)

        self._stored.set_default(linstor_url=None)

        self.framework.observe(self.on.linstor_relation_changed, self._on_linstor_relation_changed)

        self.linstor_csi_image = OCIImageResource(self, "linstor-csi-image")
        self.csi_attacher_image = OCIImageResource(self, "csi-attacher-image")
        self.csi_liveness_probe_image = OCIImageResource(self, "csi-liveness-probe-image")
        self.csi_provisioner_image = OCIImageResource(self, "csi-provisioner-image")
        self.csi_resizer_image = OCIImageResource(self, "csi-resizer-image")
        self.csi_snapshotter_image = OCIImageResource(self, "csi-snapshotter-image")

        self.framework.observe(self.on.install, self._set_pod_spec)
        self.framework.observe(self.on.upgrade_charm, self._set_pod_spec)
        self.framework.observe(self.on.config_changed, self._set_pod_spec)

    def _set_pod_spec(self, event: charm.HookEvent):
        try:
            linstor_csi_image = self.linstor_csi_image.fetch()
            csi_attacher_image = self.csi_attacher_image.fetch()
            csi_liveness_probe_image = self.csi_liveness_probe_image.fetch()
            csi_provisioner_image = self.csi_provisioner_image.fetch()
            csi_resizer_image = self.csi_resizer_image.fetch()
            csi_snapshotter_image = self.csi_snapshotter_image.fetch()
        except OCIImageResourceError as e:
            self.unit.status = e.status
            event.defer()
            return

        if not self._stored.linstor_url:
            self.unit.status = model.BlockedStatus("waiting for linstor relation")
            event.defer()
            return

        socket_vol = {
            "name": "socket-dir",
            "mountPath": "/run/csi",
            "emptyDir": {},
        }

        csi_env = {
            "ADDRESS": "/run/csi/csi.sock",
            "NAMESPACE": {"field": {"path": "metadata.namespace", "api-version": "v1"}},
            "NODE_NAME": {"field": {"path": "spec.nodeName", "api-version": "v1"}},
            "LS_CONTROLLERS": self._stored.linstor_url,
        }

        topology = self.config['enable-topology']  # type: bool

        if self.unit.is_leader():
            self.app.status = model.MaintenanceStatus("Setting pod spec")
            self.model.pod.set_spec(
                spec={
                    "version": 3,
                    "containers": [
                        {
                            "name": "linstor-csi-plugin",
                            "imageDetails": linstor_csi_image,
                            "args": [
                                "--csi-endpoint=unix://$(ADDRESS)",
                                "--node=$(NODE_NAME)",
                                "--linstor-endpoint=$(LS_CONTROLLERS)",
                                "--log-level=info",
                            ],
                            "volumeConfig": [socket_vol],
                            "envConfig": csi_env,
                            "kubernetes": {
                                "livenessProbe": {
                                    "failureThreshold": 3,
                                    "httpGet": {
                                        "path": "/healthz",
                                        "port": 9808,
                                        "scheme": "HTTP"
                                    },
                                    "periodSeconds": 10,
                                    "successThreshold": 1,
                                    "timeoutSeconds": 1
                                },
                            },
                        },
                        {
                            "name": "csi-attacher",
                            "imageDetails": csi_attacher_image,
                            "args": [
                                "--csi-address=$(ADDRESS)",
                                "--timeout=1m",
                                "--leader-election=true",
                                "--leader-election-namespace=$(NAMESPACE)",
                            ],
                            "volumeConfig": [socket_vol],
                            "envConfig": csi_env,
                        },
                        {
                            "name": "csi-livenessprobe",
                            "imageDetails": csi_liveness_probe_image,
                            "args": ["--csi-address=$(ADDRESS)"],
                            "volumeConfig": [socket_vol],
                            "envConfig": csi_env,
                        },
                        {
                            "name": "csi-provisioner",
                            "imageDetails": csi_provisioner_image,
                            "args": [
                                "--csi-address=$(ADDRESS)",
                                "--timeout=1m",
                                "--default-fstype=ext4",
                                f"--feature-gates=Topology={str(topology).lower()}",
                                "--leader-election=true",
                                "--leader-election-namespace=$(NAMESPACE)",
                            ],
                            "volumeConfig": [socket_vol],
                            "envConfig": csi_env,
                        },
                        {
                            "name": "csi-resizer",
                            "imageDetails": csi_resizer_image,
                            "args": [
                                "--csi-address=$(ADDRESS)",
                                "--timeout=1m",
                                "--handle-volume-inuse-error=false",
                                "--leader-election=true",
                                "--leader-election-namespace=$(NAMESPACE)",
                            ],
                            "volumeConfig": [socket_vol],
                            "envConfig": csi_env,
                        },
                        {
                            "name": "csi-snapshotter",
                            "imageDetails": csi_snapshotter_image,
                            "args": [
                                "--csi-address=$(ADDRESS)",
                                "--timeout=1m",
                                "--leader-election=true",
                                "--leader-election-namespace=$(NAMESPACE)",
                            ],
                            "volumeConfig": [socket_vol],
                            "envConfig": csi_env,
                        }
                    ],
                    "serviceAccount": {
                        "roles": [
                            {
                                "name": "csi-attacher",
                                "global": True,
                                "rules": [
                                    {'apiGroups': [''], 'resources': ['persistentvolumes'],
                                     'verbs': ['get', 'list', 'watch', 'update', 'patch']},
                                    {'apiGroups': ['storage.k8s.io'], 'resources': ['csinodes'],
                                     'verbs': ['get', 'list', 'watch']},
                                    {'apiGroups': ['storage.k8s.io'], 'resources': ['volumeattachments'],
                                     'verbs': ['get', 'list', 'watch', 'update', 'patch']},
                                    {'apiGroups': ['storage.k8s.io'], 'resources': ['volumeattachments/status'],
                                     'verbs': ['patch']},
                                ],
                            },
                            {
                                "name": "csi-provisioner",
                                "global": True,
                                "rules": [
                                    {'apiGroups': [''], 'resources': ['persistentvolumes'],
                                     'verbs': ['get', 'list', 'watch', 'create', 'delete']},
                                    {'apiGroups': [''], 'resources': ['persistentvolumeclaims'],
                                     'verbs': ['get', 'list', 'watch', 'update']},
                                    {'apiGroups': ['storage.k8s.io'], 'resources': ['storageclasses'],
                                     'verbs': ['get', 'list', 'watch']},
                                    {'apiGroups': [''], 'resources': ['events'],
                                     'verbs': ['list', 'watch', 'create', 'update', 'patch']},
                                    {'apiGroups': ['snapshot.storage.k8s.io'], 'resources': ['volumesnapshots'],
                                     'verbs': ['get', 'list']},
                                    {'apiGroups': ['snapshot.storage.k8s.io'], 'resources': ['volumesnapshotcontents'],
                                     'verbs': ['get', 'list']},
                                    {'apiGroups': ['storage.k8s.io'], 'resources': ['csinodes'],
                                     'verbs': ['get', 'list', 'watch']},
                                    {'apiGroups': ['storage.k8s.io'], 'resources': ['volumeattachments'],
                                     'verbs': ['get', 'list', 'watch']},
                                    {'apiGroups': [''], 'resources': ['nodes'], 'verbs': ['get', 'list', 'watch']},
                                ],
                            },
                            {
                                "name": "csi-snapshotter",
                                "global": True,
                                "rules": [
                                    {'apiGroups': [''], 'resources': ['events'],
                                     'verbs': ['list', 'watch', 'create', 'update', 'patch']},
                                    {'apiGroups': ['snapshot.storage.k8s.io'], 'resources': ['volumesnapshotclasses'],
                                     'verbs': ['get', 'list', 'watch']},
                                    {'apiGroups': ['snapshot.storage.k8s.io'], 'resources': ['volumesnapshotcontents'],
                                     'verbs': ['create', 'get', 'list', 'watch', 'update', 'delete']},
                                    {'apiGroups': ['snapshot.storage.k8s.io'],
                                     'resources': ['volumesnapshotcontents/status'], 'verbs': ['update']},
                                ],
                            },
                            {
                                "name": "csi-resizer",
                                "global": True,
                                "rules": [
                                    {'apiGroups': [''], 'resources': ['persistentvolumes'],
                                     'verbs': ['get', 'list', 'watch', 'update', 'patch']},
                                    {'apiGroups': [''], 'resources': ['persistentvolumeclaims'],
                                     'verbs': ['get', 'list', 'watch']},
                                    {'apiGroups': [''], 'resources': ['persistentvolumeclaims/status'],
                                     'verbs': ['update', 'patch']},
                                    {'apiGroups': [''], 'resources': ['events'],
                                     'verbs': ['list', 'watch', 'create', 'update', 'patch']},
                                ],
                            },
                            {
                                "name": "csi-leader-elector",
                                "rules": [
                                    {'apiGroups': ['coordination.k8s.io'], 'resources': ['leases'],
                                     'verbs': ['get', 'watch', 'list', 'delete', 'update', 'create']},
                                ],
                            }
                        ],
                    },
                },
            )
            self.app.status = model.ActiveStatus()

        self.unit.status = model.ActiveStatus()

    def _on_linstor_relation_changed(self, event: charm.RelationChangedEvent):
        url = event.relation.data[event.app].get("url")
        if url:
            self._stored.linstor_url = url

        self._set_pod_spec(event)


if __name__ == "__main__":
    main.main(LinstorCSIControllerCharm)
