import os
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import SingleQuotedScalarString,DoubleQuotedScalarString
import json
import random
from subprocess import run

from flask import Flask, request, jsonify

# Test:
# curl -F file=@ping.yml http://localhost:5000/iml/yaml/deploy
# curl -X DELETE http://localhost:5000/iml/yaml/deploy/1

app = Flask(__name__)

interpod_mode = 'br'
#interpod_mode = 'memif'
nf_memif_setup = False
DEFAULT_NAMESPACE = 'desire6g'
DEFAULT_CHART = './graph-chart'
SERVICES_FOLDER = "services"
DEPLOY_FOLDER = "deploys"
UPLOAD_FOLDER = 'files'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
  os.makedirs(UPLOAD_FOLDER)
if not os.path.exists(DEPLOY_FOLDER):
  os.makedirs(DEPLOY_FOLDER)

def get_next_deploy_id():
  next_id = 1
  while os.path.exists(os.path.join(DEPLOY_FOLDER, f'values-{next_id}.yaml')):
    next_id += 1
  return next_id

# TODO check on host if available
currentmemifbridge = 4
def getnextmemifbridgeid():
  global currentmemifbridge
  currentmemifbridge += 1
  return currentmemifbridge

memifid = {}
def getnextmemifid(nf):
  if nf not in memifid:
    memifid[nf] = -1
  memifid[nf] += 1
  return memifid[nf]

given_macs = []
def generate_mac():
  global given_macs
  while True:
    next_mac = "02:" + ":".join([f"{random.randint(0, 255):02x}" for x in range(5)])
    if next_mac not in given_macs:
      break
  given_macs.append(next_mac)
  return next_mac

given_ips = []
def generate_ip():
  global given_ips
  while True:
    next_ip = "10." + ".".join([f"{random.randint(0, 255)}" for x in range(3)])
    if next_ip not in given_ips:
      break
  given_ips.append(next_ip)
  return next_ip

def addiptoinit(dic, ip, intf, memifid=None, mac=None):
  # note: memifid act as a type param
  if memifid is not None and nf_memif_setup:
    if "cmd" not in dic:
      dic["cmd"] = SingleQuotedScalarString('')
    #if '/usr/bin/vpp ' not in dic["cmd"]:
      dic["cmd"] += SingleQuotedScalarString('/usr/bin/vpp unix { log /var/log/vpp/vpp-app.log full-coredump cli-listen /run/vpp/cli.sock gid vpp } api-trace {on} api-segment {gid vpp} cpu {skip-cores 4} dpdk {no-pci} socksvr {socket-name /run/vpp/api.sock};sleep 5;')
    dic["cmd"] += SingleQuotedScalarString(f'vppctl "create memif socket id {memifid+1} filename $(ls /var/lib/cni/usrspcni/*-{intf}.sock)";')
    dic["cmd"] += SingleQuotedScalarString(f'vppctl "create interface memif id {memifid} socket-id {memifid+1} slave no-zero-copy";')
    dic["cmd"] += SingleQuotedScalarString(f'vppctl "set int state memif{memifid+1}/{memifid} up";')
    dic["cmd"] += SingleQuotedScalarString(f'vppctl "set int mac address memif{memifid+1}/{memifid} {mac}";')
    dic["cmd"] += SingleQuotedScalarString(f'vppctl "set int ip address memif{memifid+1}/{memifid} {ip}/32";')
  elif memifid is None:
    if "initcmd" not in dic:
      dic["initcmd"] = SingleQuotedScalarString('')
    dic["initimage"] = "busybox:1.36"
    dic["initcmd"] += SingleQuotedScalarString(f"ip addr add {ip}/32 dev {intf};")

def addroutetoinit(srcnf, dstnf, dstintf, srcintf):
  s = next(i for i in srcnf['interfaces'] if i['interface'] == srcintf)
  d = next(i for i in dstnf['interfaces'] if i['interface'] == dstintf)
  if 'memifid' in s and nf_memif_setup:
    srcnf["cmd"] += f"vppctl \"set ip neighbor memif{s['memifid']+1}/{s['memifid']} {d['ip']} {d['mac']}\";"
    srcnf["cmd"] += f"vppctl \"ip route add {d['ip']}/32 via memif{s['memifid']+1}/{s['memifid']}\";"
    srcnf["cmd"] = SingleQuotedScalarString(srcnf["cmd"])
  elif 'memifid' not in s:
    srcnf["initcmd"] += f"arp -i {srcintf} -s {d['ip']} {d['mac']};ip route add {d['ip']}/32 dev {srcintf};"
    srcnf["initcmd"] = SingleQuotedScalarString(srcnf["initcmd"])

def addif(dic, name, type, ifindex):
  if f"{name}-{type}-{ifindex}" in dic:
    return
  n = {}
  n["type"] = type
  if type == "sriov":
    n["mac"] = SingleQuotedScalarString(generate_mac())
    n["vf"] = SingleQuotedScalarString("nvidia.com/cx6dx_vf")
  if type == "memif":
    n["bridgedomain"] = getnextmemifbridgeid()

  dic[f"{name}-{type}-{ifindex}"] = n

def getif(nf, intf):
  x = next(i for i in nf['interfaces'] if i['interface'] == intf)
  return x

def getifindex(nf, intf):
  x = next(i for i, dic in enumerate(nf['interfaces']) if dic['interface'] == intf)
  return x

def addtonf(nf, name, intf, mac=None, ip=None, memifid=None):
  if 'interfaces' not in nf:
    nf['interfaces'] = []
  x = next((i for i in nf['interfaces'] if i['interface'] == intf), None)
  if x != None:
    return

  i = {}
  i['interface'] = intf
  i['name'] = name
  if memifid is not None:
    i['memifid'] = memifid
  if mac:
    i['mac'] = SingleQuotedScalarString(mac)
  if ip:
    i['ip'] = ip
    addiptoinit(nf, ip, intf, memifid, mac)
  nf['interfaces'].append(i)

def addroutetonfr(nfrsrc, nfrdst, srcnode, dstnf, dstintfname):
  # TODO handle duplicate
  nfrdstport = getifindex(nfrdst, dstintfname)
  dstintf = getif(dstnf, dstintfname)
  nfrdst['files']['ipv4rules.cfg'] += f"R{dstintf['ip']}/32 {nfrdstport}\n"
  if srcnode != dstnf['node']:
    port = getifindex(nfrsrc, f"{srcnode}-{dstnf['node']}")
    nfrsrc['files']['ipv4rules.cfg'] += f"R{dstintf['ip']}/32 {port}\n"

def addnfr(services, node):
  if f"nfr-{node}" in services:
    return
  d = {}
  d['name'] = 'nfrouter'
  d['node'] = node
  d['files'] = {}
  d['files']['ipv6rules.cfg'] = SingleQuotedScalarString('R::/128 0')
  d['files']['ipv4rules.cfg'] = ''
  services[f"nfr-{node}"] = d

def addcmdtonfr(nfr, services, interfaces):
  nfr['cmd'] = './l3fwd-static -l 0-1 -n 4 --no-pci'
  i = 0
  for intf in nfr['interfaces']:
    if interfaces[intf['interface']]['type'] == 'memif':
      nfr['cmd'] += f" --vdev=net_memif{i},role=client,socket-abstract=no,socket=$(ls /var/lib/cni/usrspcni/*{intf['interface']}.sock)"
    else:
      nfr['cmd'] += f" --vdev=net_tap{i},iface=dtap{i},remote={intf['interface']}"
    i += 1
  nfr['cmd'] += f" -- -p 0x{int('1'*len(nfr['interfaces']), 2):x}"
  nfr['cmd'] += ' --config="'
  nfr['cmd'] += ','.join(f'({i},0,0),({i},1,1)' for i in range(len(nfr['interfaces'])))
  nfr['cmd'] += '" --mode=poll -P'
  i = 0
  for intf in nfr['interfaces']:
    servicewithtype, ifindex = intf['name'].rsplit('-', 1)
    service, type = servicewithtype.rsplit('-', 1)
    if type == 'br' or type == 'memif':
      mac = getif(services[service], intf['name'])['mac']
    elif type == 'sriov':
      mac = interfaces[f"{intf['interface'].rsplit('-', 1)[1]}-sriov"]['mac']
    nfr['cmd'] += f" --eth-dest={i},{mac}"
    i += 1
  nfr['cmd'] += ' --rule_ipv4="/opt/nfconfig/ipv4rules.cfg" --rule_ipv6="/opt/nfconfig/ipv6rules.cfg"'
  if interpod_mode == 'memif':
    nfr['cmd'] += ' --relax-rx-offload --parse-ptype'

  nfr['cmd'] = SingleQuotedScalarString(nfr['cmd'])

def cleanintf(services):
  for s in services:
    for i in services[s]['interfaces']:
      if 'ip' in i:
        del i['ip']
      if 'memifid' in i:
        del i['mac']
        del i['memifid']

def generate_values(nsd, path):
  with open(path, 'w') as f:
    data = {}
    data['services'] = {}
    data['interfaces'] = {}
    for i in nsd['lnsd']['ns']['application-functions']:
      s = {}
      s['name'] = i['af-id']
      s['node'] = i['af-node']
      data['services'][i['af-instance-id']] = s

    for g in nsd['lnsd']['ns']['forwarding_graphs']:
      for l in g['links']:
        for p in l['connection-points']:
          if p['member-connection-point-index'] == 1:
            srcid, srcifindex = p['member-if-id-ref'].split(':')
          if p['member-connection-point-index'] == 2:
            dstid, dstifindex = p['member-if-id-ref'].split(':')

        srcnf = data['services'][srcid]
        dstnf = data['services'][dstid]

        addif(data['interfaces'], srcid, interpod_mode, srcifindex)
        addif(data['interfaces'], dstid, interpod_mode, dstifindex)
        srcintf = f'{srcid}-{interpod_mode}-{srcifindex}'
        dstintf = f'{dstid}-{interpod_mode}-{dstifindex}'
        addtonf(srcnf, srcintf, srcintf, generate_mac(), generate_ip(), getnextmemifid(srcid) if interpod_mode == 'memif' else None)
        addtonf(dstnf, dstintf, dstintf, generate_mac(), generate_ip(), getnextmemifid(dstid) if interpod_mode == 'memif' else None)

        addnfr(data['services'], srcnf['node'])
        addnfr(data['services'], dstnf['node'])
        nfrsrc = data['services'][f"nfr-{srcnf['node']}"]
        nfrdst = data['services'][f"nfr-{dstnf['node']}"]
        if interpod_mode == 'memif':
          srcnf['hostpath'] = {'name': 'shared-dir', 'hostpath': f"/run/vpp/{srcid}", 'path': "/var/lib/cni/usrspcni"}
          dstnf['hostpath'] = {'name': 'shared-dir', 'hostpath': f"/run/vpp/{dstid}", 'path': "/var/lib/cni/usrspcni"}
          nfrsrc['hostpath'] = {'name': 'shared-dir', 'hostpath': f"/run/vpp/nfr-{srcnf['node']}", 'path': "/var/lib/cni/usrspcni"}
          nfrdst['hostpath'] = {'name': 'shared-dir', 'hostpath': f"/run/vpp/nfr-{dstnf['node']}", 'path': "/var/lib/cni/usrspcni"}

        addtonf(nfrsrc, srcintf, srcintf)
        addtonf(nfrdst, dstintf, dstintf)

        if srcnf['node'] != dstnf['node']:
          addif(data['interfaces'], srcnf['node'], "sriov")
          addif(data['interfaces'], dstnf['node'], "sriov")
          addtonf(nfrsrc, f"{srcnf['node']}-sriov", f"{srcnf['node']}-{dstnf['node']}")

        addroutetoinit(srcnf, dstnf, dstintf, srcintf)
        addroutetonfr(nfrsrc, nfrdst, srcnf['node'], dstnf, dstintf)

    for n in data['services'].values():
      if n['name'] == 'nfrouter':
        addcmdtonfr(n, data['services'], data['interfaces'])
      elif nf_memif_setup:
        n['cmd'] += 'sleep infinity;'

    cleanintf(data['services'])
    yaml=YAML()
    yaml.width = 4096
    yaml.default_flow_style = False
    yaml.dump(data, f)

@app.route("/iml/yaml/deploy/<id>", methods=["DELETE"])
def deleteDeployment(id):
  result = run(['helm', 'uninstall', '--namespace', DEFAULT_NAMESPACE, f'deploy-{id}'], capture_output = True, text = True)

  if result.stderr:
    return jsonify({"response": result.stderr}), 500
  else:
    return jsonify({"response": f"Succesfull deletion of the deployment with id: {id}"}), 200

@app.route("/iml/yaml/deploy", methods=["POST"])
def deploy_yaml():
  path = os.path.join(app.config['UPLOAD_FOLDER'], "uploaded.yml")
  file = request.files['file']
  file.save(path)

  with open(path, 'r') as f:
    try:
      yaml=YAML(typ='safe')
      yaml_data = yaml.load(f)

      deploy_id = get_next_deploy_id()
      values_path = os.path.join(DEPLOY_FOLDER, f'values-{deploy_id}.yaml')
      generate_values(yaml_data, values_path)

      result = run(['helm', 'install', '--namespace', DEFAULT_NAMESPACE, '--create-namespace', '--post-renderer', './kustomize.sh', '-f', values_path, f'deploy-{deploy_id}', DEFAULT_CHART], capture_output = True, text = True)

      if result.stderr:
        response = (f"Failed to deploy: {result.stderr}", 500)
      else:
        response = (f"Deployed: {yaml_data['lnsd']['ns']['name']} as id {deploy_id}", 200)

    except yaml.parser.ParserError:
      response = ("Failed to parse", 500)

  return jsonify({"response": response[0]}), response[1]

if __name__ == "__main__":
  app.run(host='0.0.0.0', debug=True)
