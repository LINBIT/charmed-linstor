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
import json
import logging

from oci_image import OCIImageResourceError
from ops import charm, framework, main, model

logger = logging.getLogger(__name__)

__version__ = "1.0.0"

_DEFAULTS = {
    "linstor-csi-image": {
        "piraeus": "quay.io/piraeusdatastore/piraeus-csi:v0.19.0",
        "linbit": "drbd.io/linstor-csi:v0.19.0",
    },
    "csi-attacher-image": {
        "piraeus": "k8s.gcr.io/sig-storage/csi-attacher:v3.4.0",
        "linbit": "k8s.gcr.io/sig-storage/csi-attacher:v3.4.0",
    },
    "csi-liveness-probe-image": {
        "piraeus": "k8s.gcr.io/sig-storage/livenessprobe:v2.6.0",
        "linbit": "k8s.gcr.io/sig-storage/livenessprobe:v2.6.0",
    },
    "csi-provisioner-image": {
        "piraeus": "k8s.gcr.io/sig-storage/csi-provisioner:v3.1.0",
        "linbit": "k8s.gcr.io/sig-storage/csi-provisioner:v3.1.0",
    },
    "csi-resizer-image": {
        "piraeus": "k8s.gcr.io/sig-storage/csi-resizer:v1.4.0",
        "linbit": "k8s.gcr.io/sig-storage/csi-resizer:v1.4.0",
    },
    "csi-snapshotter-image": {
        "piraeus": "k8s.gcr.io/sig-storage/csi-snapshotter:v5.0.1",
        "linbit": "k8s.gcr.io/sig-storage/csi-snapshotter:v5.0.1",
    },
}


class LinstorCSIControllerCharm(charm.CharmBase):
    _stored = framework.StoredState()

    def __init__(self, *args):
        super().__init__(*args)

        self._stored.set_default(linstor_url=None)

        self.framework.observe(
            self.on.linstor_relation_changed, self._on_linstor_relation_changed
        )
        self.framework.observe(
            self.on.linstor_relation_broken, self._on_linstor_relation_broken
        )

        self.framework.observe(self.on.install, self._set_pod_spec)
        self.framework.observe(self.on.upgrade_charm, self._set_pod_spec)
        self.framework.observe(self.on.config_changed, self._set_pod_spec)

    def _set_pod_spec(self, event: charm.HookEvent):
        print("enter _set_pod_spec")

        if not self._stored.linstor_url:
            self.unit.status = model.BlockedStatus("waiting for linstor relation")
            event.defer()
            return

        print("got url")

        try:
            linstor_csi_image = self.get_image("linstor-csi-image")
            csi_attacher_image = self.get_image("csi-attacher-image")
            csi_liveness_probe_image = self.get_image("csi-liveness-probe-image")
            csi_provisioner_image = self.get_image("csi-provisioner-image")
            csi_resizer_image = self.get_image("csi-resizer-image")
            csi_snapshotter_image = self.get_image("csi-snapshotter-image")
        except OCIImageResourceError as e:
            self.unit.status = e.status
            event.defer()
            return

        print("got images")

        socket_vol = {
            "name": "socket-dir",
            "mountPath": "/run/csi",
            "emptyDir": {},
        }

        csi_env = {
            "ADDRESS": "/run/csi/csi.sock",
            "NAMESPACE": {"field": {"path": "metadata.namespace", "api-version": "v1"}},
            "NODE_NAME": {"field": {"path": "spec.nodeName", "api-version": "v1"}},
            "POD_NAME": {"field": {"path": "metadata.name", "api-version": "v1"}},
            "LS_CONTROLLERS": self._stored.linstor_url,
        }

        if self.unit.is_leader():
            print("is leader, setting spec")

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
                                        "scheme": "HTTP",
                                    },
                                    "periodSeconds": 10,
                                    "successThreshold": 1,
                                    "timeoutSeconds": 1,
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
                                "--enable-capacity",
                                "--extra-create-metadata",
                                "--capacity-ownerref-level=2",
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
                        },
                    ],
                    "serviceAccount": {
                        "roles": [
                            {
                                "name": "csi-attacher",
                                "global": True,
                                "rules": [
                                    {
                                        "apiGroups": [""],
                                        "resources": ["persistentvolumes"],
                                        "verbs": [
                                            "get",
                                            "list",
                                            "watch",
                                            "update",
                                            "patch",
                                        ],
                                    },
                                    {
                                        "apiGroups": ["storage.k8s.io"],
                                        "resources": ["csinodes"],
                                        "verbs": ["get", "list", "watch"],
                                    },
                                    {
                                        "apiGroups": ["storage.k8s.io"],
                                        "resources": ["volumeattachments"],
                                        "verbs": [
                                            "get",
                                            "list",
                                            "watch",
                                            "update",
                                            "patch",
                                        ],
                                    },
                                    {
                                        "apiGroups": ["storage.k8s.io"],
                                        "resources": ["volumeattachments/status"],
                                        "verbs": ["patch"],
                                    },
                                ],
                            },
                            {
                                "name": "csi-provisioner",
                                "global": True,
                                "rules": [
                                    {
                                        "apiGroups": [""],
                                        "resources": ["persistentvolumes"],
                                        "verbs": [
                                            "get",
                                            "list",
                                            "watch",
                                            "create",
                                            "delete",
                                        ],
                                    },
                                    {
                                        "apiGroups": [""],
                                        "resources": ["persistentvolumeclaims"],
                                        "verbs": [
                                            "get",
                                            "list",
                                            "watch",
                                            "update",
                                            "patch",
                                        ],
                                    },
                                    {
                                        "apiGroups": ["storage.k8s.io"],
                                        "resources": ["storageclasses"],
                                        "verbs": ["get", "list", "watch"],
                                    },
                                    {
                                        "apiGroups": [""],
                                        "resources": ["events"],
                                        "verbs": [
                                            "list",
                                            "watch",
                                            "create",
                                            "update",
                                            "patch",
                                        ],
                                    },
                                    {
                                        "apiGroups": ["snapshot.storage.k8s.io"],
                                        "resources": ["volumesnapshots"],
                                        "verbs": ["get", "list"],
                                    },
                                    {
                                        "apiGroups": ["snapshot.storage.k8s.io"],
                                        "resources": ["volumesnapshotcontents"],
                                        "verbs": ["get", "list"],
                                    },
                                    {
                                        "apiGroups": ["storage.k8s.io"],
                                        "resources": ["csinodes"],
                                        "verbs": ["get", "list", "watch"],
                                    },
                                    {
                                        "apiGroups": ["storage.k8s.io"],
                                        "resources": ["volumeattachments"],
                                        "verbs": ["get", "list", "watch"],
                                    },
                                    {
                                        "apiGroups": [""],
                                        "resources": ["nodes"],
                                        "verbs": ["get", "list", "watch"],
                                    },
                                    {
                                        "apiGroups": [""],
                                        "resources": ["pods"],
                                        "verbs": ["get"],
                                    },
                                    {
                                        "apiGroups": ["apps"],
                                        "resources": ["replicasets"],
                                        "verbs": ["get"],
                                    },
                                    {
                                        "apiGroups": ["storage.k8s.io"],
                                        "resources": ["csistoragecapacities"],
                                        "verbs": [
                                            "get",
                                            "list",
                                            "watch",
                                            "create",
                                            "update",
                                            "patch",
                                            "delete",
                                        ],
                                    },
                                ],
                            },
                            {
                                "name": "csi-snapshotter",
                                "global": True,
                                "rules": [
                                    {
                                        "apiGroups": [""],
                                        "resources": ["events"],
                                        "verbs": [
                                            "list",
                                            "watch",
                                            "create",
                                            "update",
                                            "patch",
                                        ],
                                    },
                                    {
                                        "apiGroups": ["snapshot.storage.k8s.io"],
                                        "resources": ["volumesnapshotclasses"],
                                        "verbs": ["get", "list", "watch"],
                                    },
                                    {
                                        "apiGroups": ["snapshot.storage.k8s.io"],
                                        "resources": ["volumesnapshotcontents"],
                                        "verbs": [
                                            "create",
                                            "get",
                                            "list",
                                            "watch",
                                            "update",
                                            "patch",
                                            "delete",
                                        ],
                                    },
                                    {
                                        "apiGroups": ["snapshot.storage.k8s.io"],
                                        "resources": ["volumesnapshotcontents/status"],
                                        "verbs": ["update", "patch"],
                                    },
                                ],
                            },
                            {
                                "name": "csi-resizer",
                                "global": True,
                                "rules": [
                                    {
                                        "apiGroups": [""],
                                        "resources": ["persistentvolumes"],
                                        "verbs": [
                                            "get",
                                            "list",
                                            "watch",
                                            "update",
                                            "patch",
                                        ],
                                    },
                                    {
                                        "apiGroups": [""],
                                        "resources": ["persistentvolumeclaims"],
                                        "verbs": ["get", "list", "watch"],
                                    },
                                    {
                                        "apiGroups": [""],
                                        "resources": ["persistentvolumeclaims/status"],
                                        "verbs": ["update", "patch"],
                                    },
                                    {
                                        "apiGroups": [""],
                                        "resources": ["events"],
                                        "verbs": [
                                            "list",
                                            "watch",
                                            "create",
                                            "update",
                                            "patch",
                                        ],
                                    },
                                ],
                            },
                            {
                                "name": "csi-controller-leader-elector",
                                "rules": [
                                    {
                                        "apiGroups": ["coordination.k8s.io"],
                                        "resources": ["leases"],
                                        "verbs": [
                                            "get",
                                            "watch",
                                            "list",
                                            "delete",
                                            "update",
                                            "patch",
                                            "create",
                                        ],
                                    },
                                ],
                            },
                        ],
                    },
                },
            )
            self.app.status = model.ActiveStatus()

        self.unit.status = model.ActiveStatus()

    def _on_linstor_relation_changed(self, event: charm.RelationChangedEvent):
        url = event.relation.data[event.app].get("url")

        if self._stored.linstor_url != url:
            self._stored.linstor_url = url
            self._set_pod_spec(event)

    def _on_linstor_relation_broken(self, event: charm.RelationBrokenEvent):
        self._stored.linstor_url = None
        self._set_pod_spec(event)

    def get_image(self, name) -> dict:
        override = self.model.resources.fetch(
            "image-override"
        ).read_bytes()  # type: bytes
        override = json.loads(override)  # type: dict
        if override.get(name):
            return override.get(name)

        pull_secret = self.model.resources.fetch(
            "pull-secret"
        ).read_bytes()  # type: bytes
        if pull_secret:
            details = json.loads(pull_secret)
            image = _DEFAULTS[name]["linbit"]

            if not image.startswith("drbd.io"):
                # Some registries don't like sending login data even if no login is required.
                return {"imagePath": image}

            details["imagePath"] = image
            return details
        else:
            return {"imagePath": _DEFAULTS[name]["piraeus"]}


if __name__ == "__main__":
    main.main(LinstorCSIControllerCharm)
