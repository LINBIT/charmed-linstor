# LINSTOR®

## Description
This Bundle deploys [LINSTOR] on Kubernetes clusters and configures the CSI Driver.

LINSTOR developed by LINBIT®, is a software that manages replicated volumes across a group of machines

LINSTOR system consists of multiple server and client components. A LINSTOR controller manages the configuration of the
LINSTOR cluster and all of its managed storage resources. The LINSTOR satellite component manages creation, modification
and deletion of storage resources on each node that provides or uses storage resources managed by LINSTOR.

The storage system integrates with Kubernetes via a CSI Driver. Storage can be managed via Kubernetes objects such as 
`StorageClass` and `PersistentVolumeClaim`. 

## Get started

```
$ juju deploy ch:linstor
```

As a [LINBIT] customer, you are entitled to use the container images hosted on [drbd.io](http://drbd.io). These images
give you access to prebuilt DRBD modules for your kernel, a Web UI for LINSTOR and more.

To use your entitlement with Charms, create a file containing your pull credentials `linbit.secret` and
an overlay for the bundle `linbit-overlay.yaml`;

```
$ cat <<EOF > linbit.secret
{
  "username": "<user>",
  "password": "<password>"
}
$ cat <<EOF > linbit-overlay.yaml
applications:
  linstor-controller:
    charm: ch:linstor-controller
    resources:
      pull-secret: ./linbit.secret
  linstor-csi-controller:
    charm: ch:linstor-csi-controller
    resources:
      pull-secret: ./linbit.secret
  linstor-csi-node:
    charm: ch:linstor-csi-node
    resources:
      pull-secret: ./linbit.secret
  linstor-ha-controller:
    charm: ch:linstor-ha-controller
    resources:
      pull-secret: ./linbit.secret
  linstor-satellite:
    charm: ch:linstor-satellite
    resources:
      pull-secret: ./linbit.secret
EOF
$ juju deploy ch:linstor --overlay linbit-overlay.yaml
```

## Usage

The LINSTOR bundle takes care of setting up communication between components. There is a one-time initial setup when
installing LINSTOR, see ["Initial steps"](#initial-steps) below.

You can access the LINSTOR management CLI either by executing it from the Controller container:

```
$ kubectl exec -it deployment/linstor-controller -- linstor interactive
```

or by exposing the LINSTOR API (and Web UI) to the host and pointing your local LINSTOR client or browser at it.
This requires an [ingress controller](https://kubernetes.io/docs/concepts/services-networking/ingress-controllers/)
to be installed.

```
$ juju config linstor-controller juju-external-hostname=linstor.ingress.example.com
$ juju expose linstor-controller
# Access the management API via the command line
$ linstor --controllers http://linstor.ingress.example.com interactive
# Or browse the Web UI at http://linstor.ingress.example.com/ui/
```

**NOTE:** Ensure that the API and Web UI is only accessible to trusted clients.

### Initial steps

After all containers are up and running, you need to configure storage pools for your nodes. You can either do this
manually, or via a configuration option on the `linstor-satellite` charm.

#### Automatically create storage pools via configuration options

Creating storage pools via configuration options is a good way to get started with LINSTOR. It is limited to a uniform
node pool, i.e. all nodes in your cluster have disks and/or preconfigured LVM/ZFS pools under the same path.

For example, to set up a LINSTOR storage pools named `thin1` using existing LVM thinpools `vg1/thin1`, run:

```
juju config linstor-satellite storage-pools="provider=LVM_THIN,provider_name=vg1/thin1,name=thin1"
```

You can also create storage pools from raw disks. For example, to set up ZFS pools on disks `/dev/sdc` and `/dev/sdd`, run:

```
juju config linstor-satellite storage-pools=provider=ZFS_THIN,provider_name=zpool1,name=zpool1,devices=/dev/sdc,devices=/dev/sdd
```

All options are described on the [LINSTOR Satellite page.](https://charmhub.io/linstor-satellite)

#### Manually create storage pools via the management CLI

This is the recommended way if your nodes don't share the same storage configuration, for example if not all of your
nodes have extra disks for LINSTOR to use. In that case you will want to follow the [LINSTOR User Guide](https://linbit.com/drbd-user-guide/linstor-guide-1_0-en/#s-storage_pools)
on setting up storage pools.

Access the LINSTOR management CLI by running:

```
$ kubectl exec -it deployment/linstor-controller -- linstor interactive
```

## Storage classes

After you set up your storage pools you can create storage classes for LINSTOR.

A simple example, using the storage pools named `zpool1` and replicating volume data on two nodes looks like this:

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: linstor-2-replicas
provisioner: linstor.csi.linbit.com
volumeBindingMode: WaitForFirstConsumer
parameters:
  linstor.csi.linbit.com/storagePool: zpool1
  linstor.csi.linbit.com/placementCount: "2"
  csi.storage.k8s.io/fstype: xfs
```

A description of all parameters is available [here.](https://linbit.com/drbd-user-guide/linstor-guide-1_0-en/#s-kubernetes-sc-parameters)

To create a persistent volume using this storage class, we need a PersistentVolumeClaim, and a consuming Pod:

```yaml
---
kind: PersistentVolumeClaim
apiVersion: v1
metadata:
  name: linstor-volume-1
spec:
  storageClassName: linstor-2-replicas
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 500Mi
---
apiVersion: v1
kind: Pod
metadata:
  name: linstor-consumer
spec:
  containers:
  - name: alpine
    image: alpine
    command:
      - tail
      - -f
      - /dev/null
    volumeMounts:
    - name: linstor-volume
      mountPath: /data
  volumes:
  - name: linstor-volume
    persistentVolumeClaim:
      claimName: linstor-volume-1
```

## Further information

For further information, such as snapshots, S3 backups and more, please check the [LINSTOR User Guide](https://linbit.com/drbd-user-guide/linstor-guide-1_0-en/#ch-kubernetes)

[LINSTOR]: https://linbit.com/linstor/
[LINBIT]: https://linbit.com
