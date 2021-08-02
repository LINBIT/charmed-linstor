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


class LinstorCSINodeCharm(charm.CharmBase):
    _stored = framework.StoredState()

    def __init__(self, *args):
        super().__init__(*args)

        self._stored.set_default(linstor_url=None)

        self.framework.observe(self.on.linstor_relation_changed, self._on_linstor_relation_changed)
        self.framework.observe(self.on.linstor_relation_broken, self._on_linstor_relation_broken)

        self.linstor_csi_image = OCIImageResource(self, "linstor-csi-image")
        self.csi_node_driver_registrar = OCIImageResource(self, "csi-node-driver-registrar-image")
        self.csi_liveness_probe_image = OCIImageResource(self, "csi-liveness-probe-image")

        self.framework.observe(self.on.install, self._set_pod_spec)
        self.framework.observe(self.on.upgrade_charm, self._set_pod_spec)
        self.framework.observe(self.on.config_changed, self._set_pod_spec)

    def _set_pod_spec(self, event: charm.HookEvent):
        try:
            linstor_csi_image = self.linstor_csi_image.fetch()
            csi_node_driver_registrar = self.csi_node_driver_registrar.fetch()
            csi_liveness_probe_image = self.csi_liveness_probe_image.fetch()
        except OCIImageResourceError as e:
            self.unit.status = e.status
            event.defer()
            return

        if not self._stored.linstor_url:
            self.unit.status = model.BlockedStatus("waiting for linstor relation")
            event.defer()
            return

        plugin_dir = {
            "name": "socket-dir",
            "mountPath": "/run/csi",
            "hostPath": {
                "path": "/var/lib/kubelet/plugins/linstor.csi.linbit.com",
                "type": "DirectoryOrCreate",
            },
        }

        registration_vol = {
            "name": "registration-dir",
            "mountPath": "/registration",
            "hostPath": {
                "path": "/var/lib/kubelet/plugins_registry/",
                "type": "DirectoryOrCreate",
            },
        }

        publish_dir = {
            "name": "publish-dir",
            "mountPath": self.config["publish-path"],
            "hostPath": {
                "path": self.config["publish-path"],
                "type": "DirectoryOrCreate",
            }
        }

        dev_dir = {
            "name": "dev-dir",
            "mountPath": "/dev",
            "hostPath": {
                "path": "/dev",
                "type": "Directory",
            }
        }

        csi_env = {
            "ADDRESS": "/run/csi/csi.sock",
            "KUBELET_REGISTRATION_ADDRESS": "/var/lib/kubelet/plugins/linstor.csi.linbit.com/csi.sock",
            "NODE_NAME": {"field": {"path": "spec.nodeName", "api-version": "v1"}},
            "LS_CONTROLLERS": self._stored.linstor_url,
        }

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
                            "volumeConfig": [plugin_dir, dev_dir, publish_dir],
                            "envConfig": csi_env,
                            "kubernetes": {
                                "securityContext": {"privileged": True},
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
                            "name": "csi-node-driver-registrar",
                            "imageDetails": csi_node_driver_registrar,
                            "args": [
                                "--csi-address=$(ADDRESS)",
                                "--kubelet-registration-path=$(KUBELET_REGISTRATION_ADDRESS)",
                            ],
                            "volumeConfig": [plugin_dir, registration_vol],
                            "envConfig": csi_env,
                            "kubernetes": {
                                "securityContext": {"privileged": True},
                            },
                        },
                        {
                            "name": "csi-livenessprobe",
                            "imageDetails": csi_liveness_probe_image,
                            "args": ["--csi-address=$(ADDRESS)"],
                            "volumeConfig": [plugin_dir],
                            "envConfig": csi_env,
                        },
                    ],
                    "serviceAccount": {
                        "roles": [
                            {
                                "name": "csi-node-driver-registar",
                                "global": True,
                                "rules": [
                                    {'apiGroups': ['storage.k8s.io'], 'resourceNames': ['linstor.csi.linbit.com'],
                                     'resources': ['csidrivers'], 'verbs': ['get', 'update', 'patch', 'delete']},
                                    {'apiGroups': ['storage.k8s.io'], 'resources': ['csidrivers'],
                                     'verbs': ['create', 'list', 'watch']},
                                ],
                            },
                            {
                                "name": "csi-node",
                                "global": True,
                                "rules": [
                                    {'apiGroups': ['security.openshift.io', 'policy'], 'resourceNames': ['privileged'],
                                     'resources': ['securitycontextconstraints', 'podsecuritypolicies'],
                                     'verbs': ['use']},
                                ]
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


if __name__ == "__main__":
    main.main(LinstorCSINodeCharm)
