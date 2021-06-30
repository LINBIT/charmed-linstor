# Charmed Linstor

Charmed Operators for Kubernetes to deploy a LINSTOR cluster.

# Development

Follow the intructions [here](https://juju.is/docs/sdk/dev-setup).

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

To deploy charmed linstor, create a new model

```
$ juju add-model linstor
Added 'linstor' model with credential 'k8s' for user 'admin'
```

# Install charms

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
```

Now you will have the LINSTOR controller charm waiting and a database relation, and the CSI charms waiting for a
controller relation. The following commands configures these relations.

```
$ juju status
Model    Controller  Cloud/Region  Version  SLA          Timestamp
linstor  k8s         k8s           2.9.7    unsupported  16:21:21+02:00

App                     Version                    Status   Scale  Charm                   Store     Channel  Rev  OS          Address        Message
linstor-controller                                 blocked      1  linstor-controller      local                0  kubernetes                 waiting for database relation
linstor-csi-controller                             blocked      1  linstor-csi-controller  local                0  kubernetes                 waiting for linstor relation
linstor-csi-node                                   blocked      1  linstor-csi-node        local                0  kubernetes                 waiting for linstor relation
linstor-satellite       linstor-satellite:v1.13.0  active       2  linstor-satellite       local                4  kubernetes
postgresql-k8s          .../postgresql@ed0e37f     active       1  postgresql-k8s          charmhub  stable     3  kubernetes  10.233.14.102

Unit                       Workload  Agent  Address         Ports     Message
linstor-controller/0*      blocked   idle                             waiting for database relation
linstor-csi-controller/0*  blocked   idle                             waiting for linstor relation
linstor-csi-node/0*        blocked   idle                             waiting for linstor relation
linstor-satellite/0*       active    idle   192.168.122.11  3366/TCP
linstor-satellite/1        active    idle   192.168.122.10  3366/TCP
postgresql-k8s/0*          active    idle   10.233.84.6     5432/TCP  Pod configured
$ juju add-relation linstor-controller:database postgresql-k8s:db
$ juju add-relation linstor-controller:linstor-api linstor-csi-controller:linstor
$ juju add-relation linstor-controller:linstor-api linstor-csi-node:linstor
$ # Wait a bit, and everything should be ready to go
$ juju status
Model    Controller  Cloud/Region  Version  SLA          Timestamp
linstor  k8s         k8s           2.9.7    unsupported  16:26:52+02:00

App                     Version                     Status  Scale  Charm                   Store     Channel  Rev  OS          Address        Message
linstor-controller      linstor-controller:v1.13.0  active      1  linstor-controller      local                0  kubernetes  10.233.3.13
linstor-csi-controller  linstor-csi:v0.13.1         active      1  linstor-csi-controller  local                0  kubernetes
linstor-csi-node        linstor-csi:v0.13.1         active      2  linstor-csi-node        local                0  kubernetes
linstor-satellite       linstor-satellite:v1.13.0   active      2  linstor-satellite       local                5  kubernetes
postgresql-k8s          .../postgresql@ed0e37f      active      1  postgresql-k8s          charmhub  stable     3  kubernetes  10.233.14.102

Unit                       Workload  Agent  Address         Ports     Message
linstor-controller/0*      active    idle   10.233.77.12    3370/TCP
linstor-csi-controller/0*  active    idle   10.233.77.14
linstor-csi-node/0*        active    idle   10.233.77.15
linstor-csi-node/1         active    idle   10.233.84.7
linstor-satellite/8*       active    idle   192.168.122.10  3366/TCP
linstor-satellite/9        active    idle   192.168.122.11  3366/TCP
postgresql-k8s/0*          active    idle   10.233.84.6     5432/TCP  Pod configured
$ # We should also add the satellites to the controller, which can also be done using a relation
$ juju add-relation linstor-controller:linstor-api linstor-satellite:controller
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
