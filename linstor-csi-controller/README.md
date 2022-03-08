# LINSTOR® CSI Controller

## Description
This Charm deploys a LINSTOR CSI Controller on Kubernetes clusters.

The CSI Controller is part of a CSI driver for [LINSTOR]. It enables using LINSTOR to provision standard kubernetes
resources (StorageClasses, PersistentVolumeClaims)

## Usage
This Charm is part of a [LINSTOR bundle] that includes all components for a fully operational LINSTOR cluster on
Kubernetes.

Add a LINSTOR CSI Controller to your cluster:
```
$ juju deploy ch:linstor-csi-controller
```

A LINSTOR CSI Controller requires connection to the LINSTOR API:
```
$ juju add-relation linstor-controller:linstor-api linstor-csi-controller:linstor
```

[LINSTOR]: https://linbit.com/linstor/
[LINSTOR bundle]: https://charmhub.io/linstor
