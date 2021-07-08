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
```

A LINSTOR CSI Node requires connection to the LINSTOR API:
```
$ juju add-relation linstor-controller:linstor-api linstor-csi-node:linstor
```

This will create a daemon set, i.e. every node in the kubernetes cluster will
start one instance of this application.

## Requirements

Every LINSTOR CSI Node instance has to run on the same node as a registered
[LINSTOR Satellite](../linstor-satellite). If no matching Satellite is configured
on the Controller, the pod will continuously crash until the satellite becomes
available.

## Configuration
N/A
