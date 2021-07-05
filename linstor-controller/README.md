# LINSTOR Controller

## Description
This Charm deploys a [LINSTOR] Controller on Kubernetes clusters.

## Usage
This Charm is part of a [bundle] that includes all components for a fully operational LINSTOR cluster on Kubernetes.

Follow these steps to add just a LINSTOR Controller to your cluster:
```
$ juju deploy linstor-controller
```

A LINSTOR Controller requires a database to store information about the cluster and any volumes provision in it. This
charm currently supports using the [`postgresql-k8s`] charm to provide that database.
```
$ juju add-relation linstor-controller:database postgresql-k8s:db
```

[LINSTOR]: https://linbit.com/linstor/
[`postgresql-k8s`]: https://charmhub.io/postgresql-k8s
