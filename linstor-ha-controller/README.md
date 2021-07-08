# LINSTOR HA Controller

## Description
This Charm deploys LINSTOR High-Availability Controller on Kubernetes clusters.

The [LINSTOR High-Availability Controller] speeds up failover of stateful workloads in
cases of storage outages.

[LINSTOR High-Availability Controller]: https://linbit.com/drbd-user-guide/linstor-guide-1_0-en/#s-kubernetes-ha-controller

## Usage
This Charm will be part of a [bundle] that includes all components for a fully operational LINSTOR cluster on Kubernetes.

Follow these steps to add just a LINSTOR Controller to your cluster:
```
$ juju deploy ./linstor-ha-controller.charm
```

The [LINSTOR High-Availability Controller] needs to communicate with the LINSTOR Controller. To
connect the two charms, run:

```
$ juju add-relation linstor-controller:linstor-api linstor-ha-controller:linstor
```

## Configuration
N/A
