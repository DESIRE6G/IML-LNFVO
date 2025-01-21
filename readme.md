# Start LNFVO
./venv/bin/python nfvo-api.py

# Deploy nsd
curl -F file=@<nsd-name>.yml http://localhost:5000/iml/yaml/deploy

This will generate the values.yaml in the deploy folder and deploy the graph-chart with it.
The generated values can be used to redeploy after chart deletion:
helm install --namespace desire6g --create-namespace <release-name> --post-renderer ./kustomize.sh -f <values-path> ./graph-chart/

# Verify
kubectl get -n desire6g pods -o wide

# Stop
kubectl delete namespace desire6g

# Execute commands inside container
kubectl exec -it deploy/<name> -- /bin/bash # or /bin/sh

# Ping
Deploy interpod or internode nsd and ping from inside the container to the dst ip

# Prereqs
* configured hugepages
* configured sr-iov vf-s on nodes with sriov-network-device-plugin
* configured vpp on nodes, if needed
