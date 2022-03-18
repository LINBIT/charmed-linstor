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

## Usage

For the next steps, check the [docs](https://charmhub.io/linstor/docs) to learn how to configure and use storage in
your cluster.
