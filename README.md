# Charmed Linstor

Charmed Operators for Kubernetes to deploy a LINSTOR cluster.

# Usage

The charms are currently ***only available by building from source***. That also means no all-in-one bundle
(for now).

To build the charms, install [`charmcraft`] and run the following command in the checked out repository:

```
$ for charmmeta in */metadata.yaml ; do charmcraft pack -p $(dirname $charmmeta); done
Created 'linstor-controller.charm'.
Created 'linstor-csi-controller.charm'.
Created 'linstor-csi-node.charm'.
Created 'linstor-ha-controller.charm'.
Created 'linstor-satellite.charm'.
```

Now, assuming you have `juju` already configured for your cluster, run:

```
$ juju add-model linstor
$ juju deploy postgresql-k8s
$ juju deploy ./linstor-controller.charm --resource linstor-controller-image=examples/linstor-controller.json
$ juju deploy ./linstor-satellite.charm --resource linstor-satellite-image=examples/linstor-satellite.json --resource drbd-injector-image=examples/drbd-injector.json --config compile-module=true
$ juju deploy ./linstor-csi-controller.charm --resource linstor-csi-image=examples/linstor-csi-controller.json --resource csi-snapshotter-image=k8s.gcr.io/sig-storage/csi-snapshotter:v3.0.3 --resource csi-resizer-image=k8s.gcr.io/sig-storage/csi-resizer:v1.1.0 --resource csi-provisioner-image=k8s.gcr.io/sig-storage/csi-provisioner:v2.1.2 --resource csi-liveness-probe-image=k8s.gcr.io/sig-storage/livenessprobe:v2.2.0 --resource csi-attacher-image=k8s.gcr.io/sig-storage/csi-attacher:v3.1.0
$ juju deploy ./linstor-csi-node.charm --resource linstor-csi-image=examples/linstor-csi-node.json --resource csi-node-driver-registrar-image=k8s.gcr.io/sig-storage/csi-node-driver-registrar:v2.3.0 --config publish-path=/var/snap/microk8s/common/var/lib/kubelet/
$ juju trust linstor-csi-node --scope=cluster
$ juju deploy ./linstor-ha-controller.charm --resource linstor-ha-controller-image=examples/linstor-ha-controller.json
$ juju add-relation linstor-controller:database postgresql-k8s:db
$ juju add-relation linstor-controller:linstor-api linstor-csi-controller:linstor
$ juju add-relation linstor-controller:linstor-api linstor-csi-node:linstor
$ juju add-relation linstor-satellite:satellite linstor-csi-node:satellite
$ juju add-relation linstor-controller:linstor-api linstor-ha-controller:linstor
```

For more information, take a look at the READMEs in each directory.

[`charmcraft`]: https://github.com/canonical/charmcraft

# Development

## MicroK8s Quickstart (using snaps :scream:)

Follow the instructions [here](https://juju.is/docs/sdk/dev-setup).

TLDR:

```
$ snap install --classic microk8s
2021-07-02T07:24:29Z INFO Waiting for automatic snapd restart...
microk8s (1.21/stable) v1.21.1 from Canonical✓ installed
$ microk8s enable storage dns rbac
$ snap alias microk8s.kubectl kubectl
Added:
  - microk8s.kubectl as kubectl
$ snap alias microk8s.juju juju
Added:
  - microk8s.juju as juju
$ juju bootstrap microk8s micro
Creating Juju controller "micro" on microk8s/localhost
Bootstrap to Kubernetes cluster identified as microk8s/localhost
Fetching Juju Dashboard 0.7.1
Creating k8s resources for controller "controller-micro"
Downloading images
Starting controller pod
Bootstrap agent now started
Contacting Juju controller at 10.152.183.196 to verify accessibility...

Bootstrap complete, controller "micro" is now available in namespace "controller-micro"

Now you can run
	juju add-model <model-name>
to create a new model to deploy k8s workloads.
```

You can skip the next section and go directly to [Install Charms](#install-charms)

## Other K8s clusters

If you are feeling adventurous, or you hate snaps, you can follow these instructions instead:

```
$ # Download juju cli from https://launchpad.net/juju/+download (insert appropriate URL below
$ curl -fsSL https://launchpad.net/juju/2.9/2.9.7/+download/juju-2.9.7-linux-amd64.tar.xz | tar -xvJC ~/.local/bin
./juju
$ juju version
2.9.7-genericlinux-amd64
$ pip install --user charmcraft
...
$ charmcraft version
1.0.0
```

Now add your k8s cluster to juju and bootstrap:

```
# Ensure kubectl is configured and has admin rights
$ kubectl get nodes
...
$ # Add the kubernetes cluster to juju (can be skipped if using microk8s)
$ juju add-k8s --context-name $(kubectl config current-context) --client k8s
k8s substrate added as cloud "k8s" with storage provisioned
by the existing "local-storage" storage class.
You can now bootstrap to this cloud by running 'juju bootstrap k8s'.
$ juju bootstrap k8s
Creating Juju controller "k8s" on k8s
Bootstrap to generic Kubernetes cluster
Fetching Juju Dashboard 0.7.1
Creating k8s resources for controller "controller-k8s"
Downloading images
Starting controller pod
Bootstrap agent now started
Contacting Juju controller at 10.233.58.89 to verify accessibility...
Bootstrap complete, controller "k8s" is now available in namespace "controller-k8s"

Now you can run
	juju add-model <model-name>
to create a new model to deploy k8s workloads.
```

# Install charms

To deploy charmed linstor, create a new model

```
$ juju add-model linstor
Added 'linstor' model with credential 'k8s' for user 'admin'
```

First you have to build the charms. You will have to re-build them if you make any changes

```
$ charmcraft build -f linstor-controller
Created 'linstor-controller.charm'.
$ charmcraft build -f linstor-satellite
Created 'linstor-satellite.charm'.
$ charmcraft build -f linstor-csi-controller
Created 'linstor-csi-controller.charm'.
$ charmcraft build -f linstor-csi-node
Created 'linstor-csi-node.charm'.
```

Then you can deploy them. `juju` expects the images to be referenced as resources. See [`./example`](./examples) for how
you can reference images from private registries.

```
$ # Linstor requires a database. Right now only the postgres-k8s charm is supported
$ juju deploy postgresql-k8s
Located charm "postgresql-k8s" in charm-hub, revision 3
Deploying "postgresql-k8s" from charm-hub charm "postgresql-k8s", revision 3 in channel stable
$ juju deploy ./linstor-controller.charm --resource linstor-controller-image=examples/linstor-controller.json
Located local charm "linstor-controller", revision 0
Deploying "linstor-controller" from local charm "linstor-controller", revision 0
$ # Check out examples/drbd-injector.json to make sure you are using the right image for your distribution
$ # If your kernel is supported, you can set --config compile-module=false
$ juju deploy ./linstor-satellite.charm --resource linstor-satellite-image=examples/linstor-satellite.json --resource drbd-injector-image=examples/drbd-injector.json --config compile-module=true
Located local charm "linstor-satellite", revision 0
Deploying "linstor-satellite" from local charm "linstor-satellite", revision 0
$ # We can specify public image (like the ones for CSI) directly
$ juju deploy ./linstor-csi-controller.charm --resource linstor-csi-image=examples/linstor-csi-controller.json --resource csi-snapshotter-image=k8s.gcr.io/sig-storage/csi-snapshotter:v3.0.3 --resource csi-resizer-image=k8s.gcr.io/sig-storage/csi-resizer:v1.1.0 --resource csi-provisioner-image=k8s.gcr.io/sig-storage/csi-provisioner:v2.1.2 --resource csi-liveness-probe-image=k8s.gcr.io/sig-storage/livenessprobe:v2.2.0 --resource csi-attacher-image=k8s.gcr.io/sig-storage/csi-attacher:v3.1.0
Located local charm "linstor-csi-controller", revision 0
Deploying "linstor-csi-controller" from local charm "linstor-csi-controller", revision 0
$ juju deploy ./linstor-csi-node.charm --resource linstor-csi-image=examples/linstor-csi-node.json --resource csi-node-driver-registrar-image=k8s.gcr.io/sig-storage/csi-node-driver-registrar:v2.1.0 --resource csi-liveness-probe-image=k8s.gcr.io/sig-storage/livenessprobe:v2.2.0
Located local charm "linstor-csi-node", revision 0
Deploying "linstor-csi-node" from local charm "linstor-csi-node", revision 0
$ juju deploy ./linstor-ha-controller.charm --resource linstor-ha-controller-image=examples/linstor-ha-controller.json
Located local charm "linstor-ha-controller", revision 0
Deploying "linstor-ha-controller" from local charm "linstor-ha-controller", revision 0
```

Now you will have the LINSTOR controller charm waiting and a database relation, and the CSI charms waiting for a
controller relation. The following commands configures these relations.

```
$ juju status
Model    Controller  Cloud/Region        Version  SLA          Timestamp
linstor  micro       microk8s/localhost  2.9.0    unsupported  12:54:37Z

App                     Version                    Status   Scale  Charm                   Store     Channel  Rev  OS          Address  Message
linstor-controller                                 blocked      1  linstor-controller      local                0  kubernetes           waiting for database relation
linstor-csi-controller                             blocked      1  linstor-csi-controller  local                0  kubernetes           waiting for linstor relation
linstor-csi-node                                   blocked      1  linstor-csi-node        local                0  kubernetes           waiting for linstor relation
linstor-ha-controller                              blocked      1  linstor-ha-controller   local                0  kubernetes           waiting for linstor relation
linstor-satellite       linstor-satellite:v1.13.0  active       1  linstor-satellite       local                0  kubernetes
postgresql-k8s          .../postgresql@ed0e37f     active       1  postgresql-k8s          charmhub  stable     3  kubernetes

Unit                       Workload  Agent  Address       Ports     Message
linstor-controller/0*      blocked   idle                           waiting for database relation
linstor-csi-controller/0*  blocked   idle                           waiting for linstor relation
linstor-csi-node/0*        blocked   idle                           waiting for linstor relation
linstor-ha-controller/0*   blocked   idle                           waiting for linstor relation
linstor-satellite/0*       active    idle   10.43.224.37  3366/TCP
postgresql-k8s/0*          active    idle   10.1.142.163  5432/TCP  Pod configured
$ juju add-relation linstor-controller:database postgresql-k8s:db
$ juju add-relation linstor-controller:linstor-api linstor-csi-controller:linstor
$ juju add-relation linstor-controller:linstor-api linstor-csi-node:linstor
$ juju add-relation linstor-controller:linstor-api linstor-ha-controller:linstor
$ # Wait a bit, and everything should be ready to go
$ juju status
Model    Controller  Cloud/Region        Version  SLA          Timestamp
linstor  micro       microk8s/localhost  2.9.0    unsupported  13:03:34Z

App                     Version                         Status  Scale  Charm                   Store     Channel  Rev  OS          Address        Message
linstor-controller      linstor-controller:v1.13.0      active      1  linstor-controller      local                1  kubernetes  10.152.183.69
linstor-csi-controller  linstor-csi:v0.13.1             active      1  linstor-csi-controller  local                0  kubernetes
linstor-csi-node        linstor-csi:v0.13.1             active      1  linstor-csi-node        local                0  kubernetes
linstor-ha-controller   linstor-k8s-ha-controller:v...  active      1  linstor-ha-controller   local                0  kubernetes
linstor-satellite       linstor-satellite:v1.13.0       active      1  linstor-satellite       local                0  kubernetes
postgresql-k8s          .../postgresql@ed0e37f          active      1  postgresql-k8s          charmhub  stable     3  kubernetes

Unit                       Workload  Agent  Address       Ports     Message
linstor-controller/1*      active    idle   10.1.142.157  3370/TCP
linstor-csi-controller/0*  active    idle   10.1.142.158
linstor-csi-node/0*        active    idle   10.1.142.153
linstor-ha-controller/0*   active    idle   10.1.142.180
linstor-satellite/0*       active    idle   10.43.224.37  3366/TCP
postgresql-k8s/0*          active    idle   10.1.142.163  5432/TCP  Pod configured
$ # We should also add the satellites to the controller, which can also be done using a relation
$ juju add-relation linstor-controller:linstor-api linstor-satellite:linstor
$ kubectl exec deployment/linstor-controller -- linstor n l
+------------------------------------------------------------------------+
| Node                | NodeType  | Addresses                   | State  |
|========================================================================|
| ubuntu-focal-k8s-10 | SATELLITE | 192.168.122.10:3366 (PLAIN) | Online |
| ubuntu-focal-k8s-11 | SATELLITE | 192.168.122.11:3366 (PLAIN) | Online |
+------------------------------------------------------------------------+
```

And that's it for now. You can create storage pools using the usual way by running the linstor command in the controller
container. `kubectl-linstor` does **_NOT_** work with charmed linstor. There are examples for storageclass/pvc/pods in
[`/examples`](./examples).

## Update

If you made changes to a charm, you can run these commands to update an existing application

```
$ # First rebuild the charm
$ charmcraft build -f linstor-csi-controller
Created 'linstor-csi-controller.charm'.
$ # Then update it
$ juju refresh --path ./linstor-csi-controller.charm linstor-csi-controller
```

## Troubleshooting

A collection of useful commands when developing

```
$ # Hopefully convince juju to continue if a charm errored out at some point. Find the name of the stuck unit with
$ # juju status, in this example linstor-controller/1
$ juju resolved linstor-controller/1
$ # If the above command didn't manage it, you may need to remove the application
$ juju remove-application linstor-controller
$ # In some cases the above also gets stuck, then you can really force it
$ juju remove-application linstor-satellite --force --no-wait
```

## Fixing charmcraft on non-ubuntu platforms

Charms build on non-ubuntu platforms are rejected by `juju deploy` for some reason. To make them compatible, you can
trick `charmcraft` into writing the wrong metadata. Simply modify the `charmcraft/utils.py` file like shown below:

```diff
--- a.local/lib/python3.9/site-packages/charmcraft/utils.py.old
+++ b.local/lib/python3.9/site-packages/charmcraft/utils.py
@@ -205,12 +205,11 @@ def create_manifest(basedir, started_at):
         'charmcraft-started-at': started_at.isoformat() + "Z",
         'bases': [
             {
-                'name': name,
-                'channel': channel,
+                'name': 'ubuntu',
+                'channel': '20.04',
                 'architectures': architectures,
             }
         ],
-
     }
     filepath = basedir / 'manifest.yaml'
     if filepath.exists():
```

You can find the file using the following command:

```
$ python3 -c "import charmcraft.utils; print(charmcraft.utils.__file__)"
/home/test/.local/lib/python3.9/site-packages/charmcraft/utils.py
```
