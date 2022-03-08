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

from oci_image import OCIImageResource, OCIImageResourceError
from ops import charm, framework, main, model

logger = logging.getLogger(__name__)

__version__ = "1.0.0-beta.1"

_DEFAULTS = {
    "linstor-csi-image": {
        "piraeus": "quay.io/piraeusdatastore/piraeus-csi:v0.18.0",
        "linbit": "drbd.io/linstor-csi:v0.18.0",
    },
    "kubectl-image": {
        "piraeus": "docker.io/bitnami/kubectl:latest",
        "linbit": "docker.io/bitnami/kubectl:latest",
    },
    "csi-node-driver-registrar-image": {
        "piraeus": "k8s.gcr.io/sig-storage/csi-node-driver-registrar:v2.5.0",
        "linbit": "k8s.gcr.io/sig-storage/csi-node-driver-registrar:v2.5.0",
    },
    "csi-liveness-probe-image": {
        "piraeus": "k8s.gcr.io/sig-storage/livenessprobe:v2.6.0",
        "linbit": "k8s.gcr.io/sig-storage/livenessprobe:v2.6.0",
    },
}


class LinstorCSINodeCharm(charm.CharmBase):
    _stored = framework.StoredState()

    def __init__(self, *args):
        super().__init__(*args)

        self._stored.set_default(linstor_url=None, satellite_app_name=None)

        self.framework.observe(
            self.on.linstor_relation_changed, self._on_linstor_relation_changed
        )
        self.framework.observe(
            self.on.linstor_relation_broken, self._on_linstor_relation_broken
        )
        self.framework.observe(
            self.on.satellite_relation_joined, self._on_satellite_relation_joined
        )
        self.framework.observe(
            self.on.satellite_relation_broken, self._on_satellite_relation_broken
        )

        self.framework.observe(self.on.config_changed, self._config_changed)

    def _config_changed(self, event: charm.HookEvent):
        try:
            linstor_csi_image = self.get_image("linstor-csi-image")
            kubectl_image = self.get_image("kubectl-image")
            csi_node_driver_registrar_image = self.get_image(
                "csi-node-driver-registrar-image"
            )
            csi_liveness_probe_image = self.get_image("csi-liveness-probe-image")
        except OCIImageResourceError as e:
            self.unit.status = e.status
            event.defer()
            return

        if not self._stored.linstor_url:
            self.unit.status = model.BlockedStatus("waiting for linstor relation")
            event.defer()
            return

        if self.unit.is_leader():
            self.app.status = model.MaintenanceStatus("Setting pod spec")

            plugin_vol = {
                "name": "plugin-dir",
                "mountPath": "/run/csi",
                "hostPath": {
                    "path": "/var/lib/kubelet/plugins/linstor.csi.linbit.com",
                    "type": "DirectoryOrCreate",
                },
            }

            publish_vol = {
                "name": "publish-dir",
                "mountPath": self.config["publish-path"],
                "hostPath": {"path": self.config["publish-path"], "type": "Directory"},
            }

            registration_vol = {
                "name": "registration-dir",
                "mountPath": "/registration",
                "hostPath": {
                    "path": "/var/lib/kubelet/plugins_registry",
                    "type": "Directory",
                },
            }

            dev_dir = {
                "name": "dev-dir",
                "mountPath": "/dev",
                "hostPath": {"path": "/dev", "type": "Directory"},
            }

            k8s_resource_dir = {
                "name": "k8s-resource-dir",
                "mountPath": "/k8s",
                "files": [
                    {
                        "path": "init.sh",
                        "content": f"""
                        set -ex
                        kubectl patch daemonsets.apps {self.app.name} --patch-file /k8s/ds.patch --field-manager charms.linbit.com/v1 
                        kubectl apply --filename /k8s/csi-driver.json --server-side=true --field-manager charms.linbit.com/v1 
                        """,
                        "mode": 0o755,
                    },
                    {
                        "path": "ds.patch",
                        "content": json.dumps(self.daemonset_patch),
                        "mode": 0o644,
                    },
                    {
                        "path": "csi-driver.json",
                        "content": json.dumps(self.csi_driver),
                        "mode": 0o644,
                    },
                ],
            }

            csi_env = {
                "ADDRESS": "/run/csi/csi.sock",
                "LS_CONTROLLERS": self._stored.linstor_url,
                "NODE_NAME": {"field": {"path": "spec.nodeName", "api-version": "v1"}},
                "PUBLISH_PATH": self.config["publish-path"],
            }

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
                            "volumeConfig": [plugin_vol, publish_vol, dev_dir],
                            "envConfig": csi_env,
                            "kubernetes": {
                                "securityContext": {"privileged": True},
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
                            "name": "csi-livenessprobe",
                            "imageDetails": csi_liveness_probe_image,
                            "args": ["--csi-address=$(ADDRESS)"],
                            "volumeConfig": [plugin_vol],
                            "envConfig": csi_env,
                        },
                        {
                            "name": "csi-node-driver-registrar",
                            "imageDetails": csi_node_driver_registrar_image,
                            "args": [
                                "--csi-address=$(ADDRESS)",
                                "--kubelet-registration-path=/var/lib/kubelet/plugins/linstor.csi.linbit.com/csi.sock",
                            ],
                            "volumeConfig": [plugin_vol, registration_vol],
                            "envConfig": csi_env,
                        },
                        {
                            "name": "patcher",
                            "imageDetails": kubectl_image,
                            "init": True,
                            "command": ["sh", "/k8s/init.sh"],
                            "volumeConfig": [k8s_resource_dir],
                        },
                        {
                            "name": "linstor-wait-satellite",
                            "init": True,
                            "imageDetails": linstor_csi_image,
                            "command": [
                                "/linstor-wait-until",
                                "satellite-online",
                                "$(NODE_NAME)",
                            ],
                            "envConfig": csi_env,
                        },
                    ],
                    "serviceAccount": {
                        "roles": [
                            {
                                "name": "csi-driver-apply",
                                "global": True,
                                "rules": [
                                    {
                                        "apiGroups": ["storage.k8s.io"],
                                        "resources": ["csidrivers"],
                                        "verbs": [
                                            "get",
                                            "list",
                                            "patch",
                                            "update",
                                            "create",
                                            "delete",
                                        ],
                                    },
                                ],
                            },
                            {
                                "name": "csi-node-daemonset-patcher",
                                "rules": [
                                    {
                                        "apiGroups": ["apps"],
                                        "resources": ["daemonsets"],
                                        "resourceNames": [self.app.name],
                                        "verbs": ["get", "patch"],
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
            self._config_changed(event)

    def _on_linstor_relation_broken(self, event: charm.RelationBrokenEvent):
        self._stored.linstor_url = None
        self._config_changed(event)

    def _on_satellite_relation_joined(self, event: charm.RelationJoinedEvent):
        logger.debug(f"joined: {event}")
        self._stored.satellite_app_name = event.app.name

    def _on_satellite_relation_broken(self, event: charm.RelationBrokenEvent):
        logger.debug(f"broken: {event}")
        self._stored.satellite_app_name = None

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

    @property
    def csi_driver(self) -> dict:
        return {
            "apiVersion": "storage.k8s.io/v1",
            "kind": "CSIDriver",
            "metadata": {
                "name": "linstor.csi.linbit.com",
                "labels": {
                    "app.kubernetes.io/component": "cluster-config",
                    "app.kubernetes.io/instance": self.app.name,
                },
            },
            "spec": {
                "attachRequired": True,
                "fsGroupPolicy": "ReadWriteOnceWithFSType",
                "podInfoOnMount": True,
                "requiresRepublish": False,
                "storageCapacity": True,
                "volumeLifecycleModes": ["Persistent"],
            },
        }

    @property
    def daemonset_patch(self) -> dict:
        return {
            "metadata": {
                "labels": {
                    "charms.linbit.com/patched": "true",
                }
            },
            "spec": {
                "template": {
                    "spec": {
                        "containers": [
                            {
                                "name": "linstor-csi-plugin",
                                "volumeMounts": [
                                    {
                                        "name": "publish-dir",
                                        "mountPropagation": "Bidirectional",
                                        "mountPath": self.config["publish-path"],
                                    }
                                ],
                            }
                        ]
                    }
                }
            },
        }


if __name__ == "__main__":
    main.main(LinstorCSINodeCharm, use_juju_for_storage=True)
