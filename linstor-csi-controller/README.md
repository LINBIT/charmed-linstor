# LINSTOR CSI Controller

## Description
This Charm deploys a LINSTOR CSI Controller on Kubernetes clusters.

The CSI Controller is part of a CSI driver for [LINSTOR]. It enables using
LINSTOR to provision standard kubernetes resources (StorageClasses, PersistentVolumeClaims)

An example for a storage class and persistent volume claim can be found
[here](../examples/storageclass.yaml) and [here](../examples/pvc.yaml).

[LINSTOR]: https://linbit.com/linstor/

## Usage
This Charm will be part of a [bundle] that includes all components for a fully operational LINSTOR cluster on Kubernetes.

Follow these steps to add just a LINSTOR CSI Controller to your cluster:
```
$ juju deploy ./linstor-csi-controller.charm
```

A LINSTOR CSI Controller requires connection to the LINSTOR API:
```
$ juju add-relation linstor-controller:linstor-api linstor-csi-controller:linstor
```

## Configuration

* `enable-topology` (default *true*): Enable the topology feature of CSI. With
  this feature enabled, persistent volumes expose a node affinity based
  on where they are deployed.
