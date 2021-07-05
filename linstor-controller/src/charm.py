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
from ops import charm, framework, main, model

logger = logging.getLogger(__name__)

__version__ = "1.0.0-alpha0"

_API_PORT = 3370


class LinstorControllerCharm(charm.CharmBase):
    _stored = framework.StoredState()

    def __init__(self, *args):
        super().__init__(*args)

        # TODO support both mysql and postgres
        self._stored.set_default(db_info=None)

        self.framework.observe(self.on.database_relation_changed, self._on_database_relation_changed)
        self.framework.observe(self.on.database_relation_broken, self._on_database_relation_broken)
        self.framework.observe(self.on.linstor_api_relation_changed, self._on_linstor_api_relation_changed)

        self.linstor_controller_image = OCIImageResource(self, "linstor-controller-image")
        self.framework.observe(self.on.install, self._set_pod_spec)
        self.framework.observe(self.on.upgrade_charm, self._set_pod_spec)
        self.framework.observe(self.on.config_changed, self._set_pod_spec)

    def _set_pod_spec(self, event: charm.HookEvent):
        try:
            linstor_controller_image = self.linstor_controller_image.fetch()
        except OCIImageResourceError as e:
            self.unit.status = e.status
            event.defer()
            return

        if not self._stored.db_info:
            self.unit.status = model.BlockedStatus("waiting for database relation")
            event.defer()
            return

        # TODO: linstor client conf + HTTP endpoint
        db_info = self._stored.db_info

        linstor_conf = toml.dumps({
            "db": {
                "connection_url":
                    f"jdbc:postgresql://{db_info['host']}:{db_info['port']}/{db_info['database']}",
                "user": db_info['user'],
                "password": db_info['password'],
            },
        })

        linstor_client_conf = f"""[global]
controllers = {self._linstor_api_url()}
"""

        linstor_election_env = {
            "K8S_AWAIT_ELECTION_ENABLED": 1,
            "K8S_AWAIT_ELECTION_NAME": self.app.name,
            "K8S_AWAIT_ELECTION_LOCK_NAME": self.app.name,
            "K8S_AWAIT_ELECTION_LOCK_NAMESPACE": {"field": {"path": "metadata.namespace", "api-version": "v1"}},
            "K8S_AWAIT_ELECTION_IDENTITY": {"field": {"path": "metadata.name", "api-version": "v1"}},
            "K8S_AWAIT_ELECTION_POD_IP": {"field": {"path": "status.podIP", "api-version": "v1"}},
            "K8S_AWAIT_ELECTION_NODE_NAME": {"field": {"path": "spec.nodeName", "api-version": "v1"}},
            "K8S_AWAIT_ELECTION_SERVICE_NAME": self.app.name,
            "K8S_AWAIT_ELECTION_SERVICE_NAMESPACE": {"field": {"path": "metadata.namespace", "api-version": "v1"}},
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
                                        "scheme": "HTTP"
                                    },
                                    "periodSeconds": 10,
                                    "successThreshold": 1,
                                    "timeoutSeconds": 1
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
                                        "resources": ["endpoints", "endpoints/restricted"],
                                        "verbs": [
                                            "create",
                                            "patch",
                                            "update",
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

    def _on_database_relation_changed(self, event: charm.RelationChangedEvent):
        if self.unit.is_leader() and event.relation.data[self.app].get("database") != self.app.name:
            event.relation.data[self.app].update({"database": self.app.name})

        old_info = self._stored.db_info

        self._stored.db_info = {
            "host": event.relation.data[event.app].get("host"),
            "port": event.relation.data[event.app].get("port"),
            "database": event.relation.data[event.app].get("database"),
            "user": event.relation.data[event.app].get("user"),
            "password": event.relation.data[event.app].get("password"),
        }

        if old_info != self._stored.db_info:
            logger.debug("db connection changed, run _set_pod_spec")
            self._set_pod_spec(event)

    def _on_database_relation_broken(self, event: charm.RelationBrokenEvent):
        self._stored.db_info = None
        self._set_pod_spec(event)

    def _on_linstor_api_relation_changed(self, event: charm.RelationChangedEvent):
        if self.unit.is_leader():
            event.relation.data[self.app]["url"] = self._linstor_api_url()

    def _linstor_api_url(self):
        return f"http://{self.app.name}.{self.model.name}.svc:{_API_PORT}"


if __name__ == "__main__":
    main.main(LinstorControllerCharm)
