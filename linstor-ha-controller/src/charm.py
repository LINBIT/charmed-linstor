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

__version__ = "1.0.0-beta.1"

_DEFAULTS = {
    "linstor-ha-controller-image": {
        "piraeus": "quay.io/piraeusdatastore/piraeus-ha-controller:v0.3.0",
        "linbit": "drbd.io/linstor-k8s-ha-controller:v0.3.0",
    }
}


class LinstorHighAvailabilityControllerCharm(charm.CharmBase):
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
        try:
            linstor_ha_controller_image = self.get_image("linstor-ha-controller-image")
        except OCIImageResourceError as e:
            self.unit.status = e.status
            event.defer()
            return

        if not self._stored.linstor_url:
            self.unit.status = model.BlockedStatus("waiting for linstor relation")
            event.defer()
            return

        env = {
            "NAME": {"field": {"path": "metadata.name", "api-version": "v1"}},
            "NAMESPACE": {"field": {"path": "metadata.namespace", "api-version": "v1"}},
            "LS_CONTROLLERS": self._stored.linstor_url,
        }

        if self.unit.is_leader():
            self.app.status = model.MaintenanceStatus("Setting pod spec")
            self.model.pod.set_spec(
                spec={
                    "version": 3,
                    "containers": [
                        {
                            "name": "linstor-wait-api",
                            "init": True,
                            "imageDetails": linstor_ha_controller_image,
                            "command": ["/linstor-wait-until", "api-online"],
                            "envConfig": env,
                        },
                        {
                            "name": "linstor-ha-controller",
                            "imageDetails": linstor_ha_controller_image,
                            "args": [
                                "--leader-election=true",
                                "--leader-election-lease-name=$(NAME)",
                                "--leader-election-namespace=$(NAMESPACE)",
                                "--v=5",
                            ],
                            "kubernetes": {
                                "livenessProbe": {
                                    "failureThreshold": 3,
                                    "httpGet": {
                                        "path": "/healthz",
                                        "port": 8080,
                                        "scheme": "HTTP",
                                    },
                                    "periodSeconds": 10,
                                    "successThreshold": 1,
                                    "timeoutSeconds": 1,
                                },
                            },
                            "envConfig": env,
                        },
                    ],
                    "serviceAccount": {
                        "roles": [
                            {
                                "name": "linstor-ha-controller-leader-elector",
                                "rules": [
                                    {
                                        "apiGroups": ["coordination.k8s.io"],
                                        "resources": ["leases"],
                                        "verbs": ["get", "update", "create"],
                                    },
                                ],
                            },
                            {
                                "name": "linstor-ha-controller",
                                "global": True,
                                "rules": [
                                    {
                                        "apiGroups": [""],
                                        "resources": ["pods"],
                                        "verbs": ["list", "watch", "delete"],
                                    },
                                    {
                                        "apiGroups": [""],
                                        "resources": ["persistentvolumeclaims"],
                                        "verbs": ["list", "watch"],
                                    },
                                    {
                                        "apiGroups": [""],
                                        "resources": ["events"],
                                        "verbs": ["create"],
                                    },
                                    {
                                        "apiGroups": ["storage.k8s.io"],
                                        "resources": ["volumeattachments"],
                                        "verbs": ["list", "watch", "delete"],
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
    main.main(LinstorHighAvailabilityControllerCharm)
