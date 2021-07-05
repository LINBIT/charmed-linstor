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
import typing
from collections import namedtuple

import kubernetes
import linstor
from oci_image import OCIImageResource, OCIImageResourceError
from ops import charm, framework, main, model

logger = logging.getLogger(__name__)

__version__ = "1.0.0-alpha0"

StoragePoolConfig = namedtuple("StoragePoolConfig", ("name", "provider", "provider_name", "devices"))


class LinstorSatelliteCharm(charm.CharmBase):
    _stored = framework.StoredState()

    def __init__(self, *args):
        super().__init__(*args)

        self._stored.set_default(linstor_url=None)

        self.linstor_satellite_image = OCIImageResource(self, "linstor-satellite-image")
        self.drbd_injector_image = OCIImageResource(self, "drbd-injector-image")

        self.framework.observe(self.on.controller_relation_changed, self._on_controller_relation_changed)
        self.framework.observe(self.on.controller_relation_departed, self._on_controller_relation_departed)

        self.framework.observe(self.on.install, self._set_pod_spec)
        self.framework.observe(self.on.upgrade_charm, self._set_pod_spec)
        self.framework.observe(self.on.config_changed, self._set_pod_spec)

    def _set_pod_spec(self, event: charm.HookEvent):
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

        if self.unit.is_leader():
            self.app.status = model.MaintenanceStatus("Setting pod spec")
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
            self.app.status = model.ActiveStatus()

        self.unit.status = model.MaintenanceStatus("Updating storage pools")
        self._ensure_storage_pools()
        self.unit.status = model.ActiveStatus()

    def _ensure_storage_pools(self):
        """Ensure each unit has the configured storage pools available"""
        if not self._stored.linstor_url:
            return

        pod = self._get_unit_pod()
        if not pod:
            logger.debug("could not find pod matching unit %s", self.unit.name)
            return

        with self._linstor_client(self._stored.linstor_url) as client:
            pool_list_response = client.storage_pool_list_raise(filter_by_nodes=[pod.spec.node_name])
            actual_pools = pool_list_response.storage_pools

        expected_pools = _parse_storage_pool_config(self.config["storage-pools"])

        for expected_pool in expected_pools:
            if any(expected_pool.name == x.name for x in actual_pools):
                logger.debug("pool %s already exists on node %s, skipping", expected_pool.name, pod.spec.node_name)
                continue

            with self._linstor_client(self._stored.linstor_url) as client:
                if expected_pool.devices:
                    resp = client.physical_storage_create_device_pool(
                        node_name=pod.spec.node_name,
                        provider_kind=expected_pool.provider,
                        device_paths=expected_pool.devices,
                        # Strip slashes from provider pool names, LINSTOR does not expect them here,
                        # i.e. a LVMTHIN pool with pool name "thinpool" will get an LV "linstor_thinpool/thinpool".
                        pool_name=expected_pool.provider_name[expected_pool.provider_name.rfind("/") + 1:],
                        storage_pool_name=expected_pool.name,
                    )
                else:
                    resp = client.storage_pool_create(
                        node_name=pod.spec.node_name,
                        storage_pool_name=expected_pool.name,
                        storage_driver=expected_pool.provider,
                        driver_pool_name=expected_pool.provider_name,
                    )
                _assert_no_linstor_error(resp)

    def _on_controller_relation_changed(self, event: charm.RelationChangedEvent):
        self._stored.linstor_url = event.relation.data[event.app].get("url")

        if not self._stored.linstor_url:
            return

        pod = self._get_unit_pod()
        if not pod:
            logger.debug("could not find pod matching unit %s", self.unit.name)
            return

        with self._linstor_client(self._stored.linstor_url) as client:
            nodes_resp = client.node_list_raise(filter_by_nodes=[pod.spec.node_name])
            if len(nodes_resp.nodes) == 0:
                create_resp = client.node_create(
                    pod.spec.node_name, linstor.sharedconsts.VAL_NODE_TYPE_STLT, pod.status.pod_ip,
                    property_dict={f"{linstor.sharedconsts.NAMESPC_AUXILIARY}/charm/registered-for": self.app.name},
                )
                _assert_no_linstor_error(create_resp)

    def _on_controller_relation_departed(self, _event: charm.RelationDepartedEvent):
        if not self._stored.linstor_url:
            return

        pod = self._get_unit_pod()
        if not pod:
            logger.debug("could not find pod matching unit %s", self.unit.name)
            return

        with self._linstor_client(self._stored.linstor_url) as client:
            logger.debug("removing satellite %s from controller", pod.spec.node_name)
            resp = client.node_delete(pod.spec.node_name)
            _assert_no_linstor_error(resp)

        self._stored.linstor_url = None

    def _get_unit_pod(self) -> typing.Optional[kubernetes.client.models.V1Pod]:
        core_v1 = _core_v1_api()
        pods = core_v1.list_namespaced_pod(
            self.model.name, label_selector=f"app.kubernetes.io/name={self.app.name}"
        )  # type: kubernetes.client.models.V1PodList

        logger.debug("Found pods %r", pods.items)

        pod: kubernetes.client.models.V1Pod
        for pod in pods.items:
            if pod.metadata.annotations.get("unit.juju.is/id") == self.unit.name:
                return pod

        return None

    def _linstor_client(self, url):
        return linstor.Linstor(
            url,
            timeout=60,
            agent_info=f"charm-operator/{self.meta.name}/{__version__}",
        )


def _parse_storage_pool_config(conf_str: str) -> typing.List[StoragePoolConfig]:
    pools = conf_str.split()

    result = []

    for pool_str in pools:
        parts = pool_str.split(",")
        pool = {
            "name": None,
            "provider": None,
            "provider_name": None,
            "devices": [],
        }

        for part in parts:
            key, val = part.split("=", 1)
            if key not in StoragePoolConfig._fields:
                raise ValueError(f"unknown key {key}, must be one of: {StoragePoolConfig._fields}")

            if key == "devices":
                pool[key].append(val)
            else:
                pool[key] = val

        if pool["name"] is None:
            raise ValueError(f"pool config {pool_str} is missing a name")
        if pool["provider"] is None:
            raise ValueError(f"pool config {pool_str} is missing a provider")

        result.append(StoragePoolConfig(
            pool["name"],
            pool["provider"],
            pool["provider_name"],
            pool["devices"],
        ))

    return result


def _assert_no_linstor_error(response: typing.List[linstor.ApiCallResponse]):
    if not linstor.Linstor.all_api_responses_no_error(response):
        raise linstor.LinstorError(f"got failure response from Linstor {response}")


def _core_v1_api() -> kubernetes.client.CoreV1Api:
    kubernetes.config.load_incluster_config()
    return kubernetes.client.CoreV1Api()


if __name__ == "__main__":
    main.main(LinstorSatelliteCharm)
