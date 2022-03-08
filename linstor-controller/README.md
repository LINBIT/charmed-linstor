# LINSTOR® Controller

## Description
Kubernetes Charm for [LINSTOR] Controllers
  
A LINSTOR controller manages the configuration of the LINSTOR cluster and all of its managed storage resources. This charm deploys a LINSTOR Controller in a pod and configures the Kubernetes backend. Other charms can create a relation with this charm to connect to the LINSTOR API.
  
LINSTOR developed by LINBIT®, is a software that manages replicated volumes across a group of machines. With native integration to Kubernetes, LINSTOR makes building, running, and controlling block storage simple. LINSTOR® is open-source software designed to manage block storage devices for large Linux server clusters. It’s used to provide persistent Linux block storage for cloudnative and hypervisor environments.

## Usage
This Charm is part of the [LINSTOR bundle] that includes all components for a fully operational LINSTOR cluster on Kubernetes.

To add just a LINSTOR Controller to your cluster run:
```
$ juju deploy ch:linstor-controller
```

Access the LINSTOR client:
```
$ kubectl exec -it deployment/linstor-controller -- linstor interactive
```

[LINSTOR]: https://linbit.com/linstor/
[LINSTOR bundle]: https://charmhub.io/linstor
