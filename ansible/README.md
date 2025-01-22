# Install Ansible
See [docs](https://docs.ansible.com/ansible/latest/installation_guide/intro_installation.html).

## Install ansible roles and collections
```bash
ansible-galaxy install -r requirements.yml
```

## Reaching the hosts
```bash
ansible all -m ping
```
Adjust `inventory.yml`. E.g. use alias from ssh config specify control and worker nodes

# Playbooks
init-k8s-cluster: install and init the cluster on nodes specified in inventory
reset-k8s-cluster: reset the cluster

## Run a playbook
```bash
ansible-playbook <playbook.yml> [-l hostname]
```
