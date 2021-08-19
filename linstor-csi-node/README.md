# LINSTOR CSI Node

## Description
This Charm deploys LINSTOR CSI Nodes on Kubernetes clusters.

The CSI Controller is part of a CSI driver for [LINSTOR]. It enables using
LINSTOR to provision standard kubernetes resources (StorageClasses, PersistentVolumeClaims)

## Usage
This Charm will be part of a [bundle] that includes all components for a fully operational LINSTOR cluster on Kubernetes.

Follow these steps to add just LINSTOR CSI Nodes to your cluster:
```
$ juju deploy ./linstor-csi-node.charm
$ # Trust this charm so it can modify it's own stateful set. This is required because we need to control some volume
$ # mount options that are only available when directly interacting with K8s.
$ # See https://discourse.charmhub.io/t/ability-to-control-mount-propagation-in-volume-config/4893
$ juju trust linstor-csi-node --scope=cluster
```

A LINSTOR CSI Node requires connection to the LINSTOR API:
```
$ juju add-relation linstor-controller:linstor-api linstor-csi-node:linstor
```

To automatically scale to available satellites

```
$ juju add-relation linstor-satellite:satellite linstor-csi-node:satellite
```

This will create a daemon set, i.e. every node in the kubernetes cluster will
start one instance of this application.

### MicroK8s

The publish path is slightly different for K8s. Pass the following config:

```
--config publish-path=/var/snap/microk8s/common/var/lib/kubelet
```

## Requirements

Every LINSTOR CSI Node instance has to run on the same node as a registered
[LINSTOR Satellite](../linstor-satellite). If no matching Satellite is configured
on the Controller, the pod will continuously crash until the satellite becomes
available.

## Configuration
N/A
