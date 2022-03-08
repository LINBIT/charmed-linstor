# LINSTOR® Satellite

## Description
This Charm deploys LINSTOR Satellites on Kubernetes clusters.

The LINSTOR satellite component manages creation, modification and deletion of storage resources on each node that provides or uses storage resources managed by LINSTOR.

LINSTOR developed by LINBIT®, is a software that manages replicated volumes across a group of machines. With native integration to Kubernetes, LINSTOR makes building, running, and controlling block storage simple. LINSTOR® is open-source software designed to manage block storage devices for large Linux server clusters. It’s used to provide persistent Linux block storage for cloudnative and hypervisor environments.

## Usage
This Charm will be part of a [LINSTOR bundle] that includes all components for a fully operational LINSTOR cluster on Kubernetes.

Follow these steps to add just a LINSTOR Controller to your cluster:
```
$ juju deploy ch:linstor-satellite
```

This will create a daemon set, i.e. every node in the kubernetes cluster will
start one instance of this application.

A LINSTOR Satellite has to be registered on a LINSTOR Controller to make it useful.
Adding a relation to a LINSTOR Controller will register the Satellite on that
controller.

```
$ juju add-relation linstor-controller:linstor-api linstor-satellite:linstor
```

## Configuration

* `linstor-control-port` (default **3366**):
  The host port opened by the satellite for communication with the LINSTOR Controller

* `compile-module` (default **false**):
  Compile the DBRD module (instead of loading from packages)


* `storage-pools` (default **""**):
  A list of storage pools to configure. Entries are space-separated, every entry is itself a comma-separated list of key-value pairs.
  The possible keys and their meaning are:
  - provider (required): LINSTOR storage pool provider, possible values are: DISKLESS, EXOS, FILE, FILE_THIN, LVM, LVM_THIN, OPENFLEX_TARGET, SPDK, ZFS, ZFS_THIN
  - name (required): The name assigned to the storage pool in LINSTOR.
  - provider_name: Provider specific name of the storage pool. For example, the name of the Volume Group for LVM pools, the zpool for ZFS pools, etc. Required except when creating a diskless pool.
  - devices: Optionally, let LINSTOR create the provider pool on the given device. Multiple devices can be specified.

      Example 1: To configure a LINSTOR LVMTHIN storage pool named "thinpool" based on an existing LVM Thin Pool "storage/thinpool", use:
        provider=LVM_THIN,provider_name=storage/thinpool,name=thinpool

      Example 2: To configure a LINSTOR ZFS storage pool named "ssds" based on unconfigured devices "/dev/sdc" and "/dev/sdd" use:
        provider=ZFS_THIN,provider_name=ssds,name=ssds,devices=/dev/sdc,devices=/dev/sdd

[LINSTOR]: https://linbit.com/linstor/
[LINSTOR bundle]: https://charmhub.io/linstor
