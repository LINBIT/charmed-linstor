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

import toml
from oci_image import OCIImageResource, OCIImageResourceError
from ops import charm, main, model

logger = logging.getLogger(__name__)

__version__ = "1.0.0-beta.1"

_API_PORT = 3370

_DEFAULTS = {
    "linstor-controller-image": {
        "piraeus": "quay.io/piraeusdatastore/piraeus-server:v1.18.0-rc.3",
        "linbit": "drbd.io/linstor-controller:v1.18.0-rc.3",
    },
}


class LinstorControllerCharm(charm.CharmBase):
    def __init__(self, *args):
        super().__init__(*args)

        self.framework.observe(
            self.on.linstor_api_relation_changed, self._on_linstor_api_relation_changed
        )

        self.framework.observe(self.on.install, self._set_pod_spec)
        self.framework.observe(self.on.upgrade_charm, self._set_pod_spec)
        self.framework.observe(self.on.config_changed, self._set_pod_spec)

    def _set_pod_spec(self, event: charm.HookEvent):
        try:
            linstor_controller_image = self.get_image("linstor-controller-image")
        except OCIImageResourceError as e:
            self.unit.status = e.status
            event.defer()
            return

        linstor_conf = toml.dumps(
            {
                "db": {"connection_url": "k8s"},
            }
        )

        linstor_client_conf = f"""[global]
controllers = {self._linstor_api_url()}
"""

        linstor_election_env = {
            "K8S_AWAIT_ELECTION_ENABLED": 1,
            "K8S_AWAIT_ELECTION_NAME": self.app.name,
            "K8S_AWAIT_ELECTION_LOCK_NAME": self.app.name,
            "K8S_AWAIT_ELECTION_LOCK_NAMESPACE": {
                "field": {"path": "metadata.namespace", "api-version": "v1"}
            },
            "K8S_AWAIT_ELECTION_IDENTITY": {
                "field": {"path": "metadata.name", "api-version": "v1"}
            },
            "K8S_AWAIT_ELECTION_POD_IP": {
                "field": {"path": "status.podIP", "api-version": "v1"}
            },
            "K8S_AWAIT_ELECTION_NODE_NAME": {
                "field": {"path": "spec.nodeName", "api-version": "v1"}
            },
            "K8S_AWAIT_ELECTION_SERVICE_NAME": self.app.name,
            "K8S_AWAIT_ELECTION_SERVICE_NAMESPACE": {
                "field": {"path": "metadata.namespace", "api-version": "v1"}
            },
            "K8S_AWAIT_ELECTION_SERVICE_PORTS_JSON": json.dumps(
                [{"name": "linstor-api", "port": _API_PORT}]
            ),
            "K8S_AWAIT_ELECTION_STATUS_ENDPOINT": ":9999",
        }

        if self.unit.is_leader():
            self.app.status = model.MaintenanceStatus("Setting pod spec")
            self.model.pod.set_spec(
                spec={
                    "version": 3,
                    "containers": [
                        {
                            "name": "linstor-controller",
                            "imageDetails": linstor_controller_image,
                            "args": ["startController"],
                            "ports": [
                                {"name": "linstor-api", "containerPort": _API_PORT},
                            ],
                            "volumeConfig": [
                                {
                                    "name": "linstor",
                                    "mountPath": "/etc/linstor",
                                    "files": [
                                        {
                                            "path": "linstor.toml",
                                            "content": linstor_conf,
                                        },
                                        {
                                            "path": "linstor-client.conf",
                                            "content": linstor_client_conf,
                                        },
                                    ],
                                }
                            ],
                            "envConfig": linstor_election_env,
                            "kubernetes": {
                                "livenessProbe": {
                                    "failureThreshold": 3,
                                    "httpGet": {
                                        "path": "/",
                                        "port": 9999,
                                        "scheme": "HTTP",
                                    },
                                    "periodSeconds": 10,
                                    "successThreshold": 1,
                                    "timeoutSeconds": 1,
                                },
                            },
                        },
                    ],
                    "serviceAccount": {
                        "roles": [
                            {
                                "name": "linstor-controller-leader-elector",
                                "rules": [
                                    {
                                        "apiGroups": ["coordination.k8s.io"],
                                        "resources": ["leases"],
                                        "verbs": [
                                            "get",
                                            "update",
                                            "create",
                                        ],
                                    },
                                    {
                                        "apiGroups": [""],
                                        "resources": [
                                            "endpoints",
                                            "endpoints/restricted",
                                        ],
                                        "verbs": [
                                            "create",
                                            "patch",
                                            "update",
                                        ],
                                    },
                                ],
                            },
                            {
                                "name": "linstor-k8s-backend-writer",
                                "global": True,
                                "rules": [
                                    {
                                        "apiGroups": ["apiextensions.k8s.io"],
                                        "resources": ["customresourcedefinitions"],
                                        "verbs": [
                                            "get",
                                            "list",
                                            "create",
                                            "delete",
                                            "update",
                                            "patch",
                                            "watch",
                                        ],
                                    },
                                    {
                                        "apiGroups": ["internal.linstor.linbit.com"],
                                        # All these resources are dedicated just to the controller, so allow any
                                        "resources": ["*"],
                                        "verbs": [
                                            "get",
                                            "list",
                                            "create",
                                            "delete",
                                            "update",
                                            "patch",
                                            "watch",
                                        ],
                                    },
                                ],
                            },
                        ],
                    },
                },
                k8s_resources={
                    "kubernetesResources": {
                        "services": [
                            {
                                "name": self.app.name,
                                "spec": {
                                    "type": "ClusterIP",
                                    "clusterIP": "",
                                    "ports": [
                                        {
                                            "name": "linstor-api",
                                            "protocol": "TCP",
                                            "port": _API_PORT,
                                            "targetPort": _API_PORT,
                                        },
                                    ],
                                },
                            },
                        ],
                    },
                },
            )
            self.app.status = model.ActiveStatus()

        self.unit.status = model.ActiveStatus()

    def _on_linstor_api_relation_changed(self, event: charm.RelationChangedEvent):
        if self.unit.is_leader():
            event.relation.data[self.app]["url"] = self._linstor_api_url()

    def _linstor_api_url(self):
        return f"http://{self.app.name}.{self.model.name}.svc:{_API_PORT}"

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
    main.main(LinstorControllerCharm)
