The LINSTOR® bundle deploys LINBIT SDS or Piraeus Data-Store on Kubernetes clusters and configures the CSI Driver.
Piraeus DS is the freely available packaging of LINBIT SDS.

LINBIT SDS/Piraeus DS, is software that manages replicated volumes across a group of machines. It contains LINSTOR and
DRBD®, both open-source projects mainly backed by LINBIT.

It consists of multiple server and client components. A LINSTOR controller manages the configuration of the LINSTOR
cluster and all of its managed storage resources. The LINSTOR satellite component manages the creation, modification,
and deletion of storage resources on each node that provides or uses storage resources managed by LINSTOR.

The storage system integrates with Kubernetes via a CSI Driver. Storage can be managed via Kubernetes objects such as
StorageClass and PersistentVolumeClaim.

## Get started with LINBIT SDS

When installing LINBIT SDS (you have an active subscription with LINBIT), you are entitled to use the container images
hosted on [drbd.io](http://drbd.io). These images give you access to prebuilt DRBD modules for your kernel, an 
additional Web UI for LINSTOR and support from the LINBIT team.

To use your entitlement with Charms, create a file containing your pull credentials named `linbit.secret`:

```
$ DRBD_IO_USERNAME=<username>
$ DRBD_IO_PASSWORD=<password>
$ cat <<EOF > linbit.secret
{
  "username": "$DRBD_IO_USERNAME",
  "password": "$DRBD_IO_PASSWORD"
}
EOF
$ juju deploy ch:linstor
```

## Get started with Piraeus Data-Store

The Charm will automatically try to load the LINBIT pull secret. To use the freely available Piraeus Data-Store,
create an empty pull secret:

```
$ touch linbit.secret
$ juju deploy ch:linstor
```

## Initial configuration

Shortly after the initial deployment all pods should be ready, all satellites and the CSI driver configured:

```
$ juju status
App                     Version                         Status  Scale  Charm                   Channel
linstor-controller      linstor-controller:v1.18.0      active      1  linstor-controller      stable
linstor-csi-controller  linstor-csi:v0.18.0             active      1  linstor-csi-controller  stable
linstor-csi-node        linstor-csi:v0.18.0             active      3  linstor-csi-node        stable
linstor-ha-controller   linstor-k8s-ha-controller:v...  active      1  linstor-ha-controller   stable
linstor-satellite       linstor-satellite:v1.18.0       active      3  linstor-satellite       stable
$ kubectl get csidriver
NAME                     ATTACHREQUIRED   PODINFOONMOUNT   STORAGECAPACITY   TOKENREQUESTS   REQUIRESREPUBLISH   MODES        AGE
linstor.csi.linbit.com   true             true             true              <unset>         false               Persistent   32d
```

To access the interactive LINSTOR command line, run:

```
$ kubectl exec -it deployment/linstor-controller -- linstor interactive
LINSTOR ==> node list
╭──────────────────────────────────────────────────────────────────╮
┊ Node           ┊ NodeType  ┊ Addresses                  ┊ State  ┊
╞══════════════════════════════════════════════════════════════════╡
┊ node-1.cluster ┊ SATELLITE ┊ 10.43.224.101:3366 (PLAIN) ┊ Online ┊
┊ node-2.cluster ┊ SATELLITE ┊ 10.43.224.102:3366 (PLAIN) ┊ Online ┊
┊ node-3.cluster ┊ SATELLITE ┊ 10.43.224.103:3366 (PLAIN) ┊ Online ┊
╰──────────────────────────────────────────────────────────────────╯
```

To complete the deployment, you need to configure some storage pools for LINSTOR to use. The easiest way is to use the
`linstor-satellite` charm configuration:

```
$ juju config linstor-satellite storage-pools=provider=LVM_THIN,provider_name=vg1/thin1,name=thin1
$ kubectl exec -it deployment/linstor-controller -- linstor storage-pool list
...
┊ thin1    ┊ node-1.cluster ┊ LVM_THIN ┊ vg1/thin1 ┊    100 GiB ┊     100 GiB ┊ True         ┊ Ok    ┊
┊ thin1    ┊ node-2.cluster ┊ LVM_THIN ┊ vg1/thin1 ┊    100 GiB ┊     100 GiB ┊ True         ┊ Ok    ┊
┊ thin1    ┊ node-3.cluster ┊ LVM_THIN ┊ vg1/thin1 ┊    100 GiB ┊     100 GiB ┊ True         ┊ Ok    ┊
```

For more advances cases, refer to the [LINSTOR User Guide](https://linbit.com/drbd-user-guide/linstor-guide-1_0-en/#s-storage_pools)

## Usage

Examples are for StorageClass, PersistentVolumeClaim and Pods are available in the [charmed-linstor source](https://github.com/linbit/charmed-linstor/tree/master/examples).

For general information on LINSTOR and the Kubernetes integration, check out [the LINSTOR Users Guide](https://linbit.com/drbd-user-guide/linstor-guide-1_0-en/#ch-kubernetes).

## Contact information

If you have questions or issues, or want to contribute to charms and bundles, head to:

* [charmed-linstor on github](https://github.com/linbit/charmed-linstor)

If you have issues with LINSTOR or the CSI driver, head over to:

* [linstor-server on github](https://github.com/linbit/linstor-server)
* [linstor-csi on github](https://github.com/piraeusdatastore/linstor-csi)

You can also join our [community slack](https://linbit-community.slack.com/join/shared_invite/enQtOTg0MTEzOTA4ODY0LTFkZGY3ZjgzYjEzZmM2OGVmODJlMWI2MjlhMTg3M2UyOGFiOWMxMmI1MWM4Yjc0YzQzYWU0MjAzNGRmM2M5Y2Q#/)
or check out our website: [LINBIT.com](https://linbit.com/)
