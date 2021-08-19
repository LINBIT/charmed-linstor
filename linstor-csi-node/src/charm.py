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

from ops import charm, framework, main, model, pebble
from kubernetes import kubernetes

logger = logging.getLogger(__name__)

__version__ = "1.0.0-alpha0"


def _k8s_client():
    kubernetes.config.load_incluster_config()
    return kubernetes.client.ApiClient()


class LinstorCSINodeCharm(charm.CharmBase):
    _stored = framework.StoredState()

    def __init__(self, *args):
        super().__init__(*args)

        self._stored.set_default(linstor_url=None, linstor_satellites=set(), satellite_app_name=None)

        self.framework.observe(self.on.linstor_relation_changed, self._on_linstor_relation_changed)
        self.framework.observe(self.on.linstor_relation_broken, self._on_linstor_relation_broken)
        self.framework.observe(self.on.satellite_relation_joined, self._on_satellite_relation_joined)
        self.framework.observe(self.on.satellite_relation_departed, self._on_satellite_relation_departed)
        self.framework.observe(self.on.satellite_relation_broken, self._on_satellite_relation_broken)

        self.framework.observe(self.on.install, self._install)
        self.framework.observe(self.on.remove, self._remove)
        self.framework.observe(self.on.config_changed, self._config_changed)

    def _install(self, event: charm.InstallEvent):
        """Create necessary resources on install"""
        self.unit.status = model.MaintenanceStatus("applying k8s resources")
        # Create the Kubernetes resources needed for the CSI Drivers
        raw_client = _k8s_client()
        storagev1beta = kubernetes.client.StorageV1beta1Api(raw_client)

        try:
            storagev1beta.create_csi_driver(self.csi_driver)
        except kubernetes.client.exceptions.ApiException as e:
            if e.status == 409:
                logger.info("csi driver already exists")
                return
            return self.raise_or_report_trust_issue(event, e)

    def _remove(self, event: charm.RemoveEvent):
        """Clean up created resources on remove"""
        raw_client = _k8s_client()
        storagev1beta = kubernetes.client.StorageV1beta1Api(raw_client)

        try:
            storagev1beta.delete_csi_driver(self.csi_driver.metadata.name)
        except kubernetes.client.exceptions.ApiException as e:
            # Ignore errors if:
            # * the resource doesn't exist in the first place
            # * We are not allowed to delete. That means we probably never created it in the first place
            if e.status not in [403, 404]:
                raise

    def _config_changed(self, event: charm.HookEvent):
        apps_api = kubernetes.client.AppsV1Api(_k8s_client())
        try:
            s = apps_api.read_namespaced_stateful_set(name=self.app.name, namespace=self.namespace)
        except kubernetes.client.exceptions.ApiException as e:
            return self.raise_or_report_trust_issue(event, e)

        if s.metadata.labels.get("charms.linbit.com/patch-applied") != "true":
            self._patch_sts(event, apps_api, s)

        if self._stored.linstor_satellites and len(self._stored.linstor_satellites) != s.spec.replicas:
            self._scale_sts(event, apps_api, s)

        if not self._stored.linstor_url:
            self.unit.status = model.BlockedStatus("waiting for linstor relation")
            event.defer()
            return

        try:
            plugin_layer = {
                "services": {
                    "linstor-csi-plugin": {
                        "override": "replace",
                        "command": (
                            # Need sh to interpret environment variables
                            "/bin/sh -c 'exec /linstor-csi "
                            "--csi-endpoint=unix:///run/csi/csi.sock "
                            f"--linstor-endpoint={self._stored.linstor_url} "
                            "--node=${KUBE_NODE_NAME}'"
                        ),
                    },
                },
            }

            plugin = self.unit.get_container("linstor-csi-plugin")
            plugin.add_layer("linstor-csi-plugin", plugin_layer, combine=True)
            if not plugin.get_service("linstor-csi-plugin").is_running():
                plugin.start("linstor-csi-plugin")
                logger.info("linstor-csi-plugin service started")

            registrar_layer = {
                "services": {
                    "csi-node-driver-registrar": {
                        "override": "replace",
                        "command": (
                            "/csi-node-driver-registrar "
                            "--csi-address=/run/csi/csi.sock "
                            f"--kubelet-registration-path={self.config['publish-path']}"
                            "/plugins/linstor.csi.linbit.com/csi.sock"
                        ),
                    }
                }
            }
            registrar = self.unit.get_container("csi-node-driver-registrar")
            registrar.add_layer("csi-node-driver-registrar", registrar_layer, combine=True)
            if not registrar.get_service("csi-node-driver-registrar").is_running():
                registrar.start("csi-node-driver-registrar")
                logger.info("csi-node-driver-registrar service started")

        except pebble.Error as e:
            logger.warning(f"pebble error: {e}")
            self.unit.status = model.MaintenanceStatus("waiting for pebble to become ready")
            event.defer()
            return

        self.unit.status = model.ActiveStatus()

    def _patch_sts(
            self, event: charm.HookEvent, apps_api: kubernetes.client.AppsV1Api, s: kubernetes.client.V1StatefulSet
    ):
        if not self.unit.is_leader():
            self.unit.status = model.MaintenanceStatus("waiting for leader to patch stateful set")
            event.defer()
            return

        self.unit.status = model.MaintenanceStatus("patching stateful set")
        s.metadata.labels["charms.linbit.com/patch-applied"] = "true"
        s.spec.template.spec.volumes.extend([
            kubernetes.client.V1Volume(
                name="publish-dir",
                host_path=kubernetes.client.V1HostPathVolumeSource(
                    path=self.config["publish-path"], type="Directory"
                ),
            ),
            kubernetes.client.V1Volume(
                name="device-dir",
                host_path=kubernetes.client.V1HostPathVolumeSource(path="/dev", type="Directory")
            ),
            kubernetes.client.V1Volume(
                name="plugin-dir",
                host_path=kubernetes.client.V1HostPathVolumeSource(
                    path="/var/lib/kubelet/plugins/linstor.csi.linbit.com", type="DirectoryOrCreate"
                ),
            ),
            kubernetes.client.V1Volume(
                name="registration-dir",
                host_path=kubernetes.client.V1HostPathVolumeSource(
                    path="/var/lib/kubelet/plugins_registry/", type="DirectoryOrCreate"
                ),
            ),
        ])

        privileged_context = kubernetes.client.V1SecurityContext(
            privileged=True
        )
        sys_admin_context = kubernetes.client.V1SecurityContext(
            privileged=True,
            capabilities=kubernetes.client.V1Capabilities(add=["SYS_ADMIN"])
        )
        node_name_var = kubernetes.client.V1EnvVar(
            name="KUBE_NODE_NAME",
            value_from=kubernetes.client.V1EnvVarSource(
                field_ref=kubernetes.client.V1ObjectFieldSelector(field_path="spec.nodeName")
            )
        )

        for container in s.spec.template.spec.containers:
            if container.name == "csi-node-driver-registrar":
                # Need privileged context to mount host volume
                container.security_context = privileged_context
                container.volume_mounts.extend([
                    kubernetes.client.V1VolumeMount(name="plugin-dir", mount_path="/run/csi"),
                    kubernetes.client.V1VolumeMount(
                        name="registration-dir",
                        mount_path="/registration",
                    ),
                ])
                container.env.extend([node_name_var])
            if container.name == "linstor-csi-plugin":
                # Need privileged + SYS_ADMIN context to mount volumes
                container.security_context = sys_admin_context
                container.volume_mounts.extend([
                    kubernetes.client.V1VolumeMount(name="plugin-dir", mount_path="/run/csi"),
                    kubernetes.client.V1VolumeMount(name="device-dir", mount_path="/dev"),
                    kubernetes.client.V1VolumeMount(
                        name="publish-dir",
                        mount_path=self.config["publish-path"],
                        mount_propagation="Bidirectional",
                    ),
                ])
                container.env.extend([node_name_var])

        try:
            apps_api.patch_namespaced_stateful_set(name=self.app.name, namespace=self.namespace, body=s)
        except kubernetes.client.exceptions.ApiException as e:
            return self.raise_or_report_trust_issue(event, e)

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

        if event.unit.name not in self._stored.linstor_satellites:
            self._stored.linstor_satellites.add(event.unit.name)
            self._config_changed(event)

    def _on_satellite_relation_departed(self, event: charm.RelationDepartedEvent):
        logger.debug(f"departed: {event}")
        if event.unit.name in self._stored.linstor_satellites:
            self._stored.linstor_satellites.discard(event.unit.name)
            self._config_changed(event)

    def _on_satellite_relation_broken(self, event: charm.RelationBrokenEvent):
        logger.debug(f"broken: {event}")
        self._stored.linstor_satellites = set()

    def raise_or_report_trust_issue(self, event: charm.HookEvent, e: kubernetes.client.exceptions.ApiException):
        if e.status == 403:
            logger.debug(f"not allowed to patch sts: {e}")
            self.unit.status = model.MaintenanceStatus(
                f"not allowed to patch STS, please run 'juju trust {self.app.name} --scope=cluster'"
            )
            event.defer()
            return

        raise e

    @property
    def namespace(self) -> str:
        with open("/var/run/secrets/kubernetes.io/serviceaccount/namespace", "r") as f:
            return f.read().strip()

    @property
    def csi_driver(self) -> kubernetes.client.V1beta1CSIDriver:
        return kubernetes.client.V1beta1CSIDriver(
            metadata=kubernetes.client.V1ObjectMeta(
                name="linstor.csi.linbit.com",
                labels={"app.kubernetes.io/component": "cluster-config", "app.kubernetes.io/instance": self.app.name},
            ),
            spec=kubernetes.client.V1beta1CSIDriverSpec(
                attach_required=True,
                pod_info_on_mount=True,
                volume_lifecycle_modes=["Persistent"],
            ),
        )

    def _scale_sts(self, event, apps_api, s):
        logger.info(f"scale for satellites {self._stored.satellite_app_name}: {self._stored.linstor_satellites}")

        if not self.unit.is_leader():
            self.unit.status = model.MaintenanceStatus("waiting for leader to patch stateful set")
            event.defer()
            return

        if not s.spec.template.spec.affinity:
            s.spec.template.spec.affinity = kubernetes.client.V1Affinity(
                pod_affinity=kubernetes.client.V1PodAffinity(
                    required_during_scheduling_ignored_during_execution=[],
                ),
                pod_anti_affinity=kubernetes.client.V1PodAntiAffinity(
                    required_during_scheduling_ignored_during_execution=[],
                ),
            )

        affinity = s.spec.template.spec.affinity

        if not any(
                term.label_selector.get("app.kubernetes.io/name") == self._stored.satellite_app_name
                for term in
                affinity.pod_affinity.required_during_scheduling_ignored_during_execution
        ):
            affinity.pod_affinity.required_during_scheduling_ignored_during_execution.extend([
                kubernetes.client.V1PodAffinityTerm(
                    topology_key="kubernetes.io/hostname",
                    label_selector=kubernetes.client.V1LabelSelector(match_labels={
                        "app.kubernetes.io/name": self._stored.satellite_app_name,
                    }),
                )
            ])
            affinity.pod_anti_affinity.required_during_scheduling_ignored_during_execution.extend([
                kubernetes.client.V1PodAffinityTerm(
                    topology_key="kubernetes.io/hostname",
                    label_selector=kubernetes.client.V1LabelSelector(match_labels={
                        "app.kubernetes.io/name": self.app.name,
                    }),
                )
            ])

        s.spec.replicas = len(self._stored.linstor_satellites)

        try:
            apps_api.patch_namespaced_stateful_set(name=self.app.name, namespace=self.namespace, body=s)
        except kubernetes.client.exceptions.ApiException as e:
            return self.raise_or_report_trust_issue(event, e)


if __name__ == "__main__":
    main.main(LinstorCSINodeCharm, use_juju_for_storage=True)
