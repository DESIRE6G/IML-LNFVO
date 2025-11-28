import os
import traceback
import sys
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import SingleQuotedScalarString,DoubleQuotedScalarString
import random
import requests
import time
from subprocess import run
from ipaddress import IPv4Network
#from yaml_patch import patch_yaml

nfrouter_mode = 't4p4s'
nf_memif_setup = False
global predeployed
global data

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

given_nfids = []
def generate_nfid():
  global given_nfids
  next_nfid = -1
  while True:
    next_nfid += 1
    if next_nfid not in given_nfids:
      break
  given_nfids.append(next_nfid)
  return next_nfid

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
    #dic["initimage"] = "busybox:1.36"
    dic["initimage"] = "desire6g/iperf3:latest"
    dic["initcmd"] += SingleQuotedScalarString(f"ip addr add {ip}/32 dev {intf};ethtool -K {intf} tx-checksumming off;")
    if dic['domain'] == 'external':
      dic["initcmd"] += SingleQuotedScalarString(f"ip link set dev {intf} mtu 1450;")

def addroutetoinit(srcnf, dstnf, dstintf, srcintf, d6g_gw, afids):
  s = next(i for i in srcnf['interfaces'] if i['interface'] == srcintf)
  if 'memifid' in s and nf_memif_setup:
    d = next(i for i in dstnf['interfaces'] if i['interface'] == dstintf)
    srcnf["cmd"] += f"vppctl \"set ip neighbor memif{s['memifid']+1}/{s['memifid']} {d['ip']} {d['mac']}\";"
    srcnf["cmd"] += f"vppctl \"ip route add {d['ip']}/32 via memif{s['memifid']+1}/{s['memifid']}\";"
    srcnf["cmd"] = SingleQuotedScalarString(srcnf["cmd"])
  elif 'memifid' not in s:
    for i, af in enumerate(afids):
      srcnf['env'][f'AF_IP_{i}'] = af
    srcnf["initcmd"] += f"ip route add {d6g_gw}/32 dev {srcintf};ip route replace default via {d6g_gw} dev {srcintf};"
    srcnf["initcmd"] = SingleQuotedScalarString(srcnf["initcmd"])

def addif(dic, name, type, ifindex=None, vfname="nvidia.com/cx6dx_vf", master=None):
  if f"{name}-{type}-{ifindex}" in dic:
    return
  n = {}
  n["type"] = type
  if type == "sriov":
    n["mac"] = SingleQuotedScalarString(generate_mac())
    n["vf"] = SingleQuotedScalarString(vfname)
  if type == "mv": #macvlan
    n['master'] = SingleQuotedScalarString(master)
  if type == "memif":
    n["bridgedomain"] = getnextmemifbridgeid()

  if ifindex is not None:
    dic[f"{name}-{type}-{ifindex}"] = n
  else:
    dic[f"{name}-{type}"] = n

def getif(nf, intf):
  x = next(i for i in nf['interfaces'] if i['interface'] == intf)
  return x

def getifindex(nf, intf):
  x = next(i for i, dic in enumerate(nf['interfaces']) if dic['interface'] == intf)
  return x

def addtonf(nf, name, intf, interpod_mode=None, nfid=None, macs=None, ips=None, ifindex=None, g_index=None):
  if 'interfaces' not in nf:
    nf['interfaces'] = []
  x = next((i for i in nf['interfaces'] if i['interface'] == intf), None)
  if x != None:
    return

  i = {}
  i['interface'] = intf
  i['name'] = name

  if interpod_mode == 'memif':
    i['memifid'] = getnextmemifid(nfid)
    addmemifmount(nf, nfid)
  if macs is not None:
    if ifindex not in macs:
      macs[ifindex] = generate_mac()
    i['mac'] = SingleQuotedScalarString(macs[ifindex])
  if ips is not None:
    if ifindex not in ips:
      ips[ifindex] = generate_ip()
    i['ip'] = ips[ifindex]
    if not nf.get('is-scalable', False):
      addiptoinit(nf, ips[ifindex], intf, i['memifid'] if interpod_mode == 'memif' else None, macs[ifindex])
  if ifindex is not None:
    nf['interfaces'].insert(int(ifindex), i)
  else:
    nf['interfaces'].append(i)

def addroutetonfr(infs, nfrsrc, nfrdst, srcnf, srcintfname, dstnf, dstintfname, dstifindex, serviceid, g_index, locationId, sites, nodes, tasrc, tadst):

  if srcnf['site'] is not None:
    if sites[srcnf['site']]['transport-type'] == 'internal':
      srcintfname = sites[srcnf['site']]['transport-interface']
    else:
      print("external")

  if dstnf['site'] is not None:
    if sites[dstnf['site']]['transport-type'] == 'internal':
      #dstintf = getif(tadst, dstintfname)
      #dstport = str(getifindex(tadst, dstintfname))
      dstport = dstifindex
      dstintfname = sites[dstnf['site']]['transport-interface']
      dstmac = sites[dstnf['site']]['nfr-mac']
    else:
      print("external")
  else:
    dstmac = getif(dstnf, dstintfname)['mac']
    dstport = str(getifindex(dstnf, dstintfname))

  if infs[srcintfname]['type'] == 'tofino':
    nfrsrcport = infs[srcintfname]['port']
  else:
    nfrsrcport = getifindex(nfrsrc, srcintfname)

  #if srcnf['site'] is not None:
  #  srcintf = getif(tasrc, srcintfname)
  #  srcport = str(getifindex(tasrc, srcintfname))
  #else:
  #  srcintf = getif(srcnf, srcintfname)
  #  srcport = str(getifindex(srcnf, srcintfname))

  if infs[dstintfname]['type'] == 'tofino':
    nfrdstport = infs[dstintfname]['port']
  else:
    nfrdstport = getifindex(nfrdst, dstintfname)

  if nfrouter_mode == 't4p4s' or nfrouter_mode == 'bmv2':

    if srcnf['domain'] != 'external' and srcnf['site'] == dstnf['site'] and srcnf['node'] == dstnf['node']:
      entry = {
          "table": "NFPortClassifier",
          "action": "NoAction",
          "keys": {"ingress_port": nfrsrcport},
          "actionParameters": {}
          }
      addcpentry(nfrsrc['entries'], entry)
      entry = {
          "table": "FWDGExecute",
          "action": "UpdateNF",
          "keys": {
            "ingress_port": nfrsrcport,
            "serviceId": serviceid,
            "nextNF": f"{srcnf['nfids'][g_index] << 8}/8"
            },
          "actionParameters": {"nfid": encodenfidport(dstnf['nfids'][g_index], int(dstport))}
          }
      addcpentry(nfrsrc['entries'], entry)
    if dstnf['domain'] == 'internal' or dstnf['site'] is not None:
      entry = {
          "table": "NFRouter",
          "action": "NFForwardMAC",
          "keys": {
            "serviceId": serviceid,
            "locationId": locationId,
            "nextNF": encodenfidport(dstnf['nfids'][g_index], int(dstport))
            },
          "actionParameters": {
            "port": nfrdstport,
            "srcMAC": nfrdst['mac'],
            "dstMAC": dstmac
            }
          }
      addcpentry(nfrdst['entries'], entry)
    elif dstnf['domain'] == 'external' and dstnf['site'] is None:
      entry = {
          "table": "NFRouter",
          "action": "NFForwardToExternal",
          "keys": {
            "serviceId": serviceid,
            "locationId": locationId,
            "nextNF": encodenfidport(dstnf['nfids'][g_index], int(dstport))
            },
          "actionParameters": {
            "port": nfrdstport,
            "srcMAC": nfrdst['mac'],
            "dstMAC": dstmac
            }
          }
      addcpentry(nfrdst['entries'], entry)
    if srcnf['node'] != dstnf['node']:
      ifname = f"{srcnf['node']}-{dstnf['node']}-0"

      if ifname in infs and infs[ifname]['type'] == 'tofino':
        port = infs[ifname]['port']
      else:
        port = getifindex(nfrsrc, ifname)

      #dstifname = f"{dstnf['node']}-{srcnf['node']}-0"
      #name = getif(nfrdst, dstifname)['name']

      if nodes.get(dstnf['node'], {}).get('sriov-capable', False):
        dstmac = infs[f"{dstnf['node']}-sriov-0"]['mac']
      else:
        dstmac = nfrdst['mac']

      entry = {
          "table": "NFRouter",
          "action": "NFForwardMAC",
          "keys": {
            "serviceId": serviceid,
            "locationId": locationId,
            "nextNF": encodenfidport(dstnf['nfids'][g_index], int(dstport))
            },
          "actionParameters": {
            "port": port,
            "srcMAC": nfrsrc['mac'],
            "dstMAC": dstmac
            }
          }
      addcpentry(nfrsrc['entries'], entry)

def changenfrtogw(nfr):
  # if bmv2
  if nfr['is_edge'] == True:
    return

  nfr['is_edge'] = True

  if 'ip' not in nfr:
    nfr['ip'] = generate_ip()

  addGWentries(nfr)

  if not nfr['predeployed']:
    infranf_name = 'd6g-gw-v4'
    #result = run(['make', '-C', './infra-nfs', infranf_name], capture_output = True, text = True)
    nfr['files'] = [
        {"name": f"{infranf_name}.p4info.txtpb", "path": f"../../infra-nfs/{infranf_name}/data-plane/{infranf_name}.p4info.txtpb"},
        {"name": f"{infranf_name}.json", "path": f"../../infra-nfs/{infranf_name}/data-plane/{infranf_name}.json"}
    ]
    nfr['cmd'] = f'/p4runtime-sh/venv/bin/python  /local-cp/local-cp.py /opt/nfconfig/{nfr["files"][0]["name"]} /opt/nfconfig/{nfr["files"][1]["name"]}'
    #nfr['cmd'] = 'trap : TERM INT; sleep infinity & wait'

def addta(services, node, domain):
  if f"ta-{node}" in services:
    return
  d = {}
  if nfrouter_mode == 'bmv2':
    d['name'] = f'simple-switch-{nfrouter_mode}'
  else:
    d['name'] = f'dpdk-{nfrouter_mode}'
  d['node'] = node
  d['domain'] = domain
  #d['mac'] = generate_mac()
  d['interfaces'] = []

  if nfrouter_mode == 't4p4s' or nfrouter_mode == 'bmv2':

    infranf_name = 'vxlan-ta'
    d['files'] = [
        {"name": f"{infranf_name}.p4info.txtpb", "path": f"../../infra-nfs/{infranf_name}/data-plane/{infranf_name}.p4info.txtpb"},
        {"name": f"{infranf_name}.json", "path": f"../../infra-nfs/{infranf_name}/data-plane/{infranf_name}.json"}
    ]

    d['entries'] = []
    d['image'] = 'desire6g/local-cp:latest'
    d['cmd'] = f'/p4runtime-sh/venv/bin/python  /local-cp/local-cp.py /opt/nfconfig/{d["files"][0]["name"]} /opt/nfconfig/{d["files"][1]["name"]}'
    #d['cmd'] = 'trap : TERM INT; sleep infinity & wait'

  services[f"ta-{node}"] = d

def addnfr(services, node, infranfs, predeployed=False):
  if f"nfr-{node}" in services:
    return
  d = {}
  d['is_edge'] = False
  d['entries'] = []
  d['predeployed'] = predeployed
  d['node'] = node
  d['mac'] = generate_mac()

  if predeployed:
    d['name'] = 'predeployed'
  else:
    if nfrouter_mode == 't4p4s' or nfrouter_mode == 'bmv2':
      setinfranf(d, 'nfrouter', nfrouter_mode)

  if infranfs:
    nfr = next((i for i in infranfs if i['instance-id'] == f"nfr-{node}"), None)
    if nfr:
      if 'static-mac' in nfr:
        d['mac'] = nfr['static-mac']
      if 'static-ip' in nfr:
        d['ip'] = nfr['static-ip']
      if predeployed:
        d['controlplane-ip'] = nfr['controlplane-ip']
        d['controlplane-port'] = nfr['controlplane-port']
        d['int-enabled'] = nfr.get('int-enabled', False)
        intfs = nfr.get('interfaces', [])
        d['interfaces'] = []
        for i in intfs:
          d['interfaces'].append({'interface': i, 'name': i})

  services[f"nfr-{node}"] = d

def setinfranf(nf, infranf_name, switch_mode):
  if switch_mode == 'bmv2':
    nf['name'] = f'simple-switch-{switch_mode}'
  else:
    nf['name'] = f'dpdk-{switch_mode}'

  #result = run(['make', '-C', './infra-nfs', infranf_name], capture_output = True, text = True)
  nf['files'] = [
      {"name": f"{infranf_name}.p4info.txtpb", "path": f"../../infra-nfs/{infranf_name}/data-plane/{infranf_name}.p4info.txtpb"},
      {"name": f"{infranf_name}.json", "path": f"../../infra-nfs/{infranf_name}/data-plane/{infranf_name}.json"}
  ]

  nf['entries'] = []
  nf['image'] = 'desire6g/local-cp:latest'
  nf['cmd'] = f'/p4runtime-sh/venv/bin/python  /local-cp/local-cp.py /opt/nfconfig/{nf["files"][0]["name"]} /opt/nfconfig/{nf["files"][1]["name"]}'
  #nf['cmd'] = 'trap : TERM INT; sleep infinity & wait'


def addcpentry(entries, entry):
  if entry not in entries:
    entries.append(entry)

def addcmdtoswitch(nfr, services, interfaces):
  anymemif = False
  ealopts = '-l 0-1 -n 4 --no-pci'
  cmdopts = ''
  bmv2opts = ''
  i = 0
  for intf in nfr['interfaces']:
    if nfrouter_mode == 'bmv2':
      bmv2opts += f" -i {i}@{intf['interface']}"
    else:
      if interfaces[intf['name']]['type'] == 'memif':
        anymemif = True
        ealopts += f" --vdev=net_memif{i},role=client,socket-abstract=no,socket=$(ls /var/lib/cni/usrspcni/*{intf['interface']}.sock)"
      else:
        ealopts += f" --vdev=net_tap{i},iface=dtap{i},remote={intf['interface']}"
    i += 1
  cmdopts += f" -p 0x{int('1'*len(nfr['interfaces']), 2):x}"

  if nfrouter_mode == 't4p4s':
    cmdopts += ' --config=\\"'
  else:
    cmdopts += ' --config="'
  cmdopts += ','.join(f'({i},0,0),({i},1,1)' for i in range(len(nfr['interfaces'])))
  if nfrouter_mode == 't4p4s':
    cmdopts += '\\"'
  else:
    cmdopts += '"'

  if nfrouter_mode == 't4p4s':
    print(f'echo "nfeal -> ealopts += { ealopts }" >> /opt/t4p4s/opts_dpdk.cfg;echo "nfports -> cmdopts += { cmdopts }" >> /opt/t4p4s/opts_dpdk.cfg;P4C=/opt/p4c P4PI=/opt/PI GRPC=/opt/grpc GRPCPP=/opt/P4Runtime_GRPCPP RTE_SDK=/opt/ /opt/t4p4s/t4p4s.sh :nf p4rt dbg verbose')
    nfr['sidecar'] = {}
    nfr['sidecar']['image'] = 'desire6g/dpdk-t4p4s:latest'
    nfr['sidecar']['cmd'] = SingleQuotedScalarString(f'echo "nfeal -> ealopts += { ealopts }" >> /opt/t4p4s/opts_dpdk.cfg;echo "nfports -> cmdopts += { cmdopts }" >> /opt/t4p4s/opts_dpdk.cfg;P4C=/opt/p4c P4PI=/opt/PI GRPC=/opt/grpc GRPCPP=/opt/P4Runtime_GRPCPP RTE_SDK=/opt/ /opt/t4p4s/t4p4s.sh :nf p4rt dbg verbose')
    #nfr['sidecar']['cmd'] = SingleQuotedScalarString('trap : TERM INT; sleep infinity & wait')
  elif nfrouter_mode == 'bmv2':
    nfr['sidecar'] = {}
    nfr['sidecar']['image'] = 'desire6g/simple-switch-bmv2:latest'
    nfr['sidecar']['cmd'] = SingleQuotedScalarString(f'simple_switch_grpc --log-console --device-id 1 {bmv2opts} /opt/nfconfig/{nfr["files"][1]["name"]} -- --grpc-server-addr 0.0.0.0:50051')
    #nfr['sidecar']['cmd'] = SingleQuotedScalarString('trap : TERM INT; sleep infinity & wait')

def cleanintf(services, unmanaged):
  for s in list(services):
    for i in services[s]['interfaces']:
      if 'ip' in i:
        del i['ip']
      if 'memifid' in i:
        del i['mac']
        del i['memifid']
    if services[s]['name'] == 'unmanaged' or services[s]['name'] == 'predeployed':
      if 'entries' in services[s]:
        unmanaged[s] = services[s]
      del services[s]

def encodenfidport(nfid: int, port: int):
  return (nfid << 8) + port

def addnf(services, nf, domain, gs, name=None, node=None, siteId=None, predeployed=False):
  if nf['instance-id'] in services:
    return
  s = {}
  s['name'] = nf['id'] if name is None else name
  s['node'] = nf['node'] if node is None else node
  s['site'] = siteId
  s['domain'] = domain
  s['predeployed'] = predeployed

  s['nfids'] = []
  if 'static-nfids' in nf:
    for val in nf['static-nfids']:
      given_nfids.append(val)
      s['nfids'].append(val)
  else:
    for _ in range(gs):
      s['nfids'].append(generate_nfid())

  s['macs'] = {}
  if 'static-macs' in nf:
    for idx, val in enumerate(nf['static-macs']):
      given_macs.append(val)
      s['macs'][str(idx)] = val

  s['ips'] = {}
  if s['domain'] == 'external' or 'static-ips' in nf:
    #s['ips'] = {}
    if 'static-ips' in nf:
      for idx, val in enumerate(nf['static-ips']):
        given_ips.append(val)
        s['ips'][str(idx)] = val

  s['interfaces'] = []
  s['is-ue'] = nf.get('is-ue', False)
  s['env'] = {}
  s['is-scalable'] = nf.get('is-scalable', False)
  if 'parent-instance' in nf:
    s['parent-instance'] = nf['parent-instance']
  if s['is-scalable']:
    s['instances'] = nf['instances']
    if 'static-instance-ips' in nf:
      s['static-instance-ips'] = nf['static-instance-ips']
    else:
      s['static-instance-ips'] = []
      for i in range(s['instances']):
        s['static-instance-ips'].append(str(next(data['macvlan-subnet'])))

    s['static-instance-nodes'] = nf['static-instance-nodes']
    s['current-instance'] = 0
    for i in range(s['instances']):
      if s['static-instance-nodes'][i] == 'external':
        continue
      addnf(services, {'id': nf['id'], 'instance-id': f"{i}--{nf['instance-id']}", 'static-ips': [s['static-instance-ips'][i]], 'parent-instance': nf['instance-id'] }, s['domain'], gs, node=s['static-instance-nodes'][i])
      if s['static-instance-nodes'][i] == s['node']:
        addtonf(data['services'][f"{i}--{nf['instance-id']}"], f"{nf['instance-id']}-{i}-br-0", f"{nf['instance-id']}-{i}-br-0", ifindex='0', macs={}, ips=data['services'][f"{i}--{nf['instance-id']}"]['ips'])
      else:
        addif(data['interfaces'], f"{nf['instance-id']}-{i}", 'mv', 0, master=data["nodes"][s['static-instance-nodes'][i]]['macvlan-master'])
        addtonf(data['services'][f"{i}--{nf['instance-id']}"], f"{nf['instance-id']}-{i}-mv-0", f"{nf['instance-id']}-{i}-mv-0", ifindex='0', macs={}, ips=data['services'][f"{i}--{nf['instance-id']}"]['ips'])

    setinfranf(s, 'af-selector', 'bmv2')

  services[nf['instance-id']] = s

def parse_siteconfig(path):
  global predeployed

  predeployed = {}
  if not os.path.isfile(path):
    predeployed['predeployed-nfs'] = []
    predeployed['predeployed-afs'] = []
    predeployed['predeployed-nfrs'] = []
    predeployed['interfaces'] = []
    predeployed['sites'] = {}
    predeployed['nodes'] = {}
    predeployed['listening-port'] = 5000
    return

  with open(path, 'r') as f:
    try:
      yaml=YAML(typ='safe')
      sconfig = yaml.load(f)
      predeployed['listening-port'] = sconfig.get('listening-port', 5000)
      predeployed['predeployed-nfs'] = sconfig['predeployed-nfs']
      predeployed['predeployed-afs'] = sconfig['predeployed-afs']
      predeployed['predeployed-nfrs'] = sconfig['predeployed-nfrs']
      predeployed['interfaces'] = sconfig['interfaces']
      if 'monitoring-ip' in sconfig:
        predeployed['monitoring-ip'] = sconfig['monitoring-ip']
        predeployed['monitoring-port'] = sconfig['monitoring-port']
      if 'SMO-ip' in sconfig:
        predeployed['SMO-ip'] = sconfig['SMO-ip']
        predeployed['SMO-port'] = sconfig['SMO-port']

      predeployed['sites'] = {}
      for i in sconfig['predeployed-tas']:
        addsite(predeployed['sites'], i)

      if 'macvlan-subnet' in sconfig:
        predeployed['macvlan-subnet'] = iter(IPv4Network(sconfig['macvlan-subnet']))

      predeployed['nodes'] = {}
      for i in sconfig['nodes']:
        node = {}
        if 'macvlan-master' in i:
          node['macvlan-master'] = i['macvlan-master']
        node['sriov-capable'] = i['sriov-capable']
        if node['sriov-capable']:
          node['sriov-vf-name'] = i['sriov-vf-name']
        predeployed['nodes'][i['id']] = node

    except Exception as ex:
      response = (f'{type(ex).__name__}: {ex.args}', 500)
      traceback.print_exc()

def addlb_uplink_entry(lbnf):
  uplink_port = 0
  entry = {
    "table": "Forwarder",
    "keys": {"instId": 0},
    "action": "forwardToUplink",
    "actionParameters": {"port": uplink_port, "nfIp": lbnf['ips']['0']}
  }
  addcpentry(lbnf['entries'], entry)

def addlb_instance_entry(nfid, lbnf, instIps, instId, type):
  instIp = instIps[instId]
  instPort = getifindex(lbnf, f'{nfid}-{instId}-{type}-0') + 1
  entry = {
    "table": "Forwarder",
    "keys": {"instId": instId + 1},
    "action": "forwardToInstance",
    "actionParameters": {"port": instPort, "instIp": instIp}
  }
  addcpentry(lbnf['entries'], entry)

def store_mgmtaddr(nfid, mgmt_ip):
  global data
  data['services'][nfid]["mgmt_ip"] = mgmt_ip

def stopAllMonitoring():
  global data
  for s in data['services']:
    if 'job-id' in s:
      stopMonitoring(s['job-id'])

def stopMonitoring(jobid):
  global data
  url = f"http://{data['monitoring-ip']}:{data['monitoring-port']}/Forecasting/deactivateJob/{jobid}"
  try:
    reply = requests.put(url)
  except:
    raise Exception(f"Monitoring error: cant reach server")
  print('reply:', x.json())
  if x.status_code != 200:
    raise Exception(f"Monitoring error: {x.json()}")

def set_scalable_instance(serviceId, jobId):
  global data

  try:
    inst = next(s for s in data['services'] if 'job-id' in data['services'][s] and data['services'][s]['job-id'] == jobId)
  except Exception as ex:
    raise Exception(f"Scale error: No NF with job id: {jobId}")

  parentNFId = data['services'][inst]['parent-instance']
  parentNF = data['services'][parentNFId]
  parentNF['current-instance'] = (parentNF['current-instance'] + 1) % parentNF['instances']

  mgmt_ip = parentNF['mgmt_ip']
  mgmt_port = 5000
  url = f'http://{mgmt_ip}:{mgmt_port}/api/tables/'

  entry = {
    "table": "InstanceSelector",
    "keys": {"dstAddr": f"{parentNF['ips']['0']} &&& 0xFFFFFFFF"},
    "action": "setInstance",
    "actionParameters": {"instId": parentNF['current-instance']+1},
    "priority": 10,
  }
  x = requests.post(url, json = entry)
  if x.status_code != 200:
    raise Exception(f"Controlplane error: {x.json()}")

  return(f"Current instance changed to: {parentNF['current-instance']}")

def set_active_instance(lbnf, instId):
  entry = {
    "table": "InstanceSelector",
    "keys": {"dstAddr": f"{lbnf['ips']['0']} &&& 0xFFFFFFFF"},
    "action": "setInstance",
    "actionParameters": {"instId": instId+1},
    "priority": 10,
  }
  addcpentry(lbnf['entries'], entry)

  for i in range(lbnf['instances']):
      entry = {
        "table": "InstanceSelector",
        "keys": {"srcAddr": f"{lbnf['static-instance-ips'][i]} &&& 0xFFFFFFFF"},
        "action": "setInstance",
        "actionParameters": {"instId": 0},
        "priority": i+1,
      }
      addcpentry(lbnf['entries'], entry)

def add_int_entries(nfr, serviceId):
  if nfr.get('int-collector', False):
    entry = {
      "table": "tb_d6gint_handler",
      "keys": {"serviceId": f"{serviceId} &&& 0xFFFF"},
      "action": "do_d6gint_update_t3_and_send_report",
      "actionParameters": {"mirror_session": nfr['int-mirror-session']}
    }
    addcpentry(nfr['entries'], entry)
  else:
    entry = {
      "table": "tb_d6gint_handler",
      "keys": {"serviceId": f"{serviceId} &&& 0xFFFF"},
      "action": "do_d6gint_update_t2",
      "actionParameters": {}
    }
    addcpentry(nfr['entries'], entry)

    #entry = {
    #  "table": "tb_clock_sync",
    #  "keys": {"count": "0"},
    #  "action": "just_forward",
    #  "actionParameters": {"port": "156"}
    #}
    #addcpentry(nfr['entries'], entry)
    #entry = {
    #  "table": "tb_clock_sync",
    #  "keys": {"count": "1"},
    #  "action": "clock_sync_add_t1",
    #  "actionParameters": {"port": "156"}
    #}
    #addcpentry(nfr['entries'], entry)
    #entry = {
    #  "table": "tb_clock_sync",
    #  "keys": {"count": "3"},
    #  "action": "clock_sync_add_t3",
    #  "actionParameters": {"port": "16"}
    #}
    #addcpentry(nfr['entries'], entry)

def addta_dec_entries(tanf, nfrdst_mac, srcintf):
  nfrport = getifindex(tanf, srcintf)
  entry = {
    "table": "vxlan_fwd",
    "keys": {"dstAddr": nfrdst_mac},
    "action": "vxlan_decap",
    "actionParameters": {"port": nfrport}
  }
  addcpentry(tanf['entries'], entry)

def addta_enc_entries(tanf, nfrsrc_mac, site, siteintf):
  siteport = getifindex(tanf, siteintf)
  entry = {
    "table": "vtep_src",
    "keys": {"srcAddr": nfrsrc_mac},
    "action": "set_vtep_src_ip",
    "actionParameters": {"vtep_src_ip": site['srcip']}
  }
  addcpentry(tanf['entries'], entry)

  entry = {
    "table": "vtep_dst",
    "keys": {"dstAddr": site['nfr-mac']},
    "action": "set_vtep_dst_ip",
    "actionParameters": {
      "vtep_dst_ip": site['dstip'],
      "smac": site['srcmac'],
      "dmac": site['dstmac'],
      "port": siteport
    }
  }
  addcpentry(tanf['entries'], entry)

def addue2smentries(nfrsrc, srcintf, graph_direction, srcnf, srcifindex, dstnf, dstifindex, g_index, graph_service_id, ueids, location_id):
  nfrsrcport = getifindex(nfrsrc, srcintf)

  entry = {
      "table": "ModeSelector",
      "action": "setUpstreamMode4" if graph_direction == 'upstream' else "setDownstreamMode4",
      "keys": {"ingress_port": nfrsrcport},
      "actionParameters": {}
      }
  addcpentry(nfrsrc['entries'], entry)

  relevantues = [srcnf['ips'][srcifindex]] if graph_direction == 'upstream' and srcnf['is-ue'] else ueids
  for ueid in relevantues:
    smentry = {
        "table": "ServiceMapper",
        "action": "setD6GService",
        "keys": {
          "ingress_port": nfrsrcport,
          "direction": 0 if graph_direction == 'upstream' else 1,
          "ueid": f"{ueid}/32"},
        "actionParameters": {
          "serviceId": graph_service_id,
          "nextNF": encodenfidport(dstnf['nfids'][g_index], int(dstifindex))
          }
        }
    addcpentry(nfrsrc['entries'], smentry)
    uemapentry = {
        "table": "UEMapper",
        "action": "UEMapping",
        "keys": {"ueid": ueid},
        "actionParameters": {"locationId": location_id}
        }
    addcpentry(nfrsrc['entries'], uemapentry)

def addGWentries(nfr):
  entry = {
      "table": "arp_responder_v4",
      "action": "arp_reply",
      "keys": {"hdr.arp.oper": 1, "hdr.arp_ipv4.tpa": nfr['ip']},
      "actionParameters": {"my_mac": nfr['mac']}
      }
  addcpentry(nfr['entries'], entry)
  entry = {
      "table": "icmp_responder_v4",
      "action": "icmp_reply",
      "keys": {"hdr.ethernet.dstAddr": nfr['mac'], "hdr.ipv4.dstAddr": nfr['ip']},
      "actionParameters": {}
      }
  addcpentry(nfr['entries'], entry)


def addsite(sites, s):
  if s['id'] in sites:
    return
  site = {}
  site['nfr-mac'] = s['nfr-mac']
  site['transport-node'] = s['transport-node']
  site['transport-type'] = s['transport-type']
  if site['transport-type'] == 'external':
    site['srcmac'] = s['srcmac']
    site['dstmac'] = s['dstmac']
    site['srcip'] = s['srcip']
    site['dstip'] = s['dstip']
  else:
    site['transport-interface'] = s['transport-interface']
  sites[s['id']] = site

def getueidsofgraph(links, graph_direction, services, afs, sites):
  # AF IPS are not neccessary treat it as a debug feature
  ueids = []
  afids = []

  for s in sites:
    for nf in s['network-functions']:
      if 'afip' in nf:
        afids.append(nf['afip'])

  for l in links:
    if graph_direction == 'upstream':
      srcid, srcifidx = l['connection-points'][0]['if-id-ref'].split(':')
      dstid, dstifidx = l['connection-points'][1]['if-id-ref'].split(':')
    else:
      dstid, dstifidx = l['connection-points'][0]['if-id-ref'].split(':')
      srcid, srcifidx = l['connection-points'][1]['if-id-ref'].split(':')
    ue_candidate = services[srcid]
    af_candidate = services[dstid]
    if ue_candidate['is-ue']:
      if srcifidx not in ue_candidate['ips']:
        ue_candidate['ips'][srcifidx] = generate_ip()
      ueids.append(ue_candidate['ips'][srcifidx])

    anyaf = False
    for i in afs:
      if af_candidate['name'] == i['id']:
        anyaf = True
        break
    if anyaf:
      if dstifidx not in af_candidate['ips']:
        af_candidate['ips'][dstifidx] = generate_ip()
      afids.append(af_candidate['ips'][dstifidx])
  return ueids, afids

def addmemifmount(nf, nfid):
  nf['hostpath'] = {'name': 'shared-dir', 'hostpath': f"/run/vpp/{nfid}", 'path': "/var/lib/cni/usrspcni"}

def generate_values(nsd, path):
  global predeployed
  global nfrouter_mode
  global data
  with open(path, 'w') as f:
    data = {}
    data['services'] = {}
    data['interfaces'] = {}
    data['sites'] = {}
    data['location-id'] = nsd['lnsd']['ns']['location-id']
    data['default-service-id'] = nsd['lnsd']['ns']['default-service-id']
    data['default-nfr-mode'] = nsd['lnsd']['ns']['default-nfrouter-mode']
    data['default-interpod-mode'] = nsd['lnsd']['ns']['default-interpod-mode']
    gs = len(nsd['lnsd']['ns']['forwarding_graphs'])
    data['nodes'] = predeployed['nodes']
    if 'macvlan-subnet' in predeployed:
      data['macvlan-subnet'] = predeployed['macvlan-subnet']

    for i in nsd['lnsd']['ns']['network-functions']:
      addnf(data['services'], i, 'internal', gs)

    for i in predeployed['predeployed-nfs']:
      addnf(data['services'], i, 'internal', gs, 'unmanaged')

    for i in predeployed['predeployed-afs']:
      addnf(data['services'], i, i['domain'], gs, 'unmanaged')

    for i in nsd['lnsd']['ns']['application-functions']:
      addnf(data['services'], i, i['domain'], gs)
      if data['services'][i['instance-id']].get('is-scalable', False):
        for j in range(data['services'][i['instance-id']]['instances']):

          if data['services'][i['instance-id']]['static-instance-nodes'][j] == i['node']:
            addif(data['interfaces'], f"{i['instance-id']}-{j}", 'br', 0)
            addtonf(data['services'][i['instance-id']], f"{i['instance-id']}-{j}-br-0", f"{i['instance-id']}-{j}-br-0")
            addlb_instance_entry(i['instance-id'], data['services'][i['instance-id']], data['services'][i['instance-id']]['static-instance-ips'], j, 'br')
          else:
            addtonf(data['services'][f"{j}--{i['instance-id']}"], f"{i['instance-id']}-{j}-mv-0", f"{i['instance-id']}-{j}-mv-0")
            addtonf(data['services'][i['instance-id']], f"{i['instance-id']}-{j}-mv-0", f"{i['instance-id']}-{j}-mv-0")
            addlb_instance_entry(i['instance-id'], data['services'][i['instance-id']], data['services'][i['instance-id']]['static-instance-ips'], j, 'mv')

        set_active_instance(data['services'][i['instance-id']], 0)

    for i in predeployed['predeployed-nfrs']:
      addnfr(data['services'], i['node'], predeployed['predeployed-nfrs'], True)
      if data['services'][i['instance-id']].get('int-enabled', False):
        add_int_entries(data['services'][i['instance-id']], data['default-service-id'])

    for i in predeployed['interfaces']:
      data['interfaces'][i['id']] = i

    data['sites'] = predeployed['sites']

    for s in nsd['lnsd']['ns']['site-connections']:
      if s['id'] not in data['sites']:
        addsite(data['sites'], s)
      for i in s['network-functions']:
        addnf(data['services'], i, 'internal', gs, 'unmanaged', data['sites'][s['id']]['transport-node'], s['id'])
      for i in s['application-functions']:
        addnf(data['services'], i, 'internal', gs, 'unmanaged', data['sites'][s['id']]['transport-node'], s['id'])

    for g_index, g in enumerate(nsd['lnsd']['ns']['forwarding_graphs']):
      nfrouter_mode = g.get('nfrouter-mode', data['default-nfr-mode'])
      graph_direction = g['direction']
      graph_service_id = g.get('service-id', data['default-service-id'])

      ueids, afids = getueidsofgraph(g['links'], graph_direction, data['services'], nsd['lnsd']['ns']['application-functions'], nsd['lnsd']['ns']['site-connections'])

      for l in g['links']:
        interpod_mode = l.get("interpod-mode", data['default-interpod-mode'])

        srcid, srcifindex = l['connection-points'][0]['if-id-ref'].split(':')
        dstid, dstifindex = l['connection-points'][1]['if-id-ref'].split(':')
        srcifindex = str(srcifindex)
        dstifindex = str(dstifindex)

        srcnf = data['services'][srcid]
        dstnf = data['services'][dstid]

        addnfr(data['services'], srcnf['node'], nsd['lnsd']['ns'].get('infra-nfs'))
        addnfr(data['services'], dstnf['node'], nsd['lnsd']['ns'].get('infra-nfs'))

        nfrsrc = data['services'][f"nfr-{srcnf['node']}"]
        nfrdst = data['services'][f"nfr-{dstnf['node']}"]

        srcintf = f'{srcid}-{interpod_mode}-{srcifindex}'
        dstintf = f'{dstid}-{interpod_mode}-{dstifindex}'
        tasrc = None
        tadst = None

        addif(data['interfaces'], srcid, interpod_mode, srcifindex)
        if l.get("is-direct", False):
          addtonf(dstnf, srcintf, srcintf, interpod_mode, srcid, srcnf['macs'], srcnf['ips'], srcifindex, g_index)
          addtonf(srcnf, srcintf, srcintf, interpod_mode, srcid, srcnf['macs'], srcnf['ips'], srcifindex, g_index)
          continue

        if srcnf['site'] is not None:
          if data['sites'][srcnf['site']]['transport-type'] == 'external':
            addta(data['services'], srcnf['node'], srcnf['domain'])
            tasrc = data['services'][f"ta-{srcnf['node']}"]
            addtonf(tasrc, srcintf, srcintf, interpod_mode, srcid, {0: data['sites'][srcnf['site']]['nfr-mac']}, [''], 0)

            addif(data['interfaces'], f"ta-{srcnf['site']}", "br", 0)
            addtonf(tasrc, f"ta-{srcnf['site']}-br-0", f"ta-{srcnf['site']}-br-0")
            addta_dec_entries(tasrc, nfrdst['mac'], srcintf)
        else:
          addtonf(srcnf, srcintf, srcintf, interpod_mode, srcid, srcnf['macs'], srcnf['ips'], srcifindex, g_index)
        addtonf(nfrsrc, srcintf, srcintf, interpod_mode, srcid)

        addif(data['interfaces'], dstid, interpod_mode, dstifindex)
        if dstnf['site'] is not None:
          if data['sites'][dstnf['site']]['transport-type'] == 'external':
            addta(data['services'], dstnf['node'], dstnf['domain'])
            tadst = data['services'][f"ta-{dstnf['node']}"]
            addtonf(tadst, dstintf, dstintf, interpod_mode, dstid, {0: data['sites'][dstnf['site']]['nfr-mac']}, [''], 0)

            addif(data['interfaces'], f"ta-{dstnf['site']}", "br", 0)
            addtonf(tadst, f"ta-{dstnf['site']}-br-0", f"ta-{dstnf['site']}-br-0")
            addta_enc_entries(tadst, nfrsrc['mac'], data['sites'][dstnf['site']], f"ta-{dstnf['site']}-br-0")
        else:
          addtonf(dstnf, dstintf, dstintf, interpod_mode, dstid, dstnf['macs'], dstnf['ips'], dstifindex, g_index)
        addtonf(nfrdst, dstintf, dstintf, interpod_mode, dstid)

        if srcnf['node'] != dstnf['node']:
          if data["nodes"].get(dstnf['node'], {}).get('sriov-capable', False):
            sriovResName = data["nodes"].get(dstnf['node'], {}).get('sriov-vf-name', None)
            addif(data['interfaces'], dstnf['node'], "sriov", 0, sriovResName)

          if data["nodes"].get(srcnf['node'], {}).get('sriov-capable', False):
            sriovResName = data["nodes"].get(srcnf['node'], {}).get('sriov-vf-name', None)
            addif(data['interfaces'], srcnf['node'], "sriov", 0, sriovResName)
            addtonf(nfrsrc, f"{srcnf['node']}-sriov-0", f"{srcnf['node']}-{dstnf['node']}-0")
            if sriovResName:
              nfrsrc['vfres'] = sriovResName
              # TODO number of req vfs
          else:
            addif(data['interfaces'], f"{srcnf['node']}-{dstnf['node']}", "br", 0)
            addtonf(nfrsrc, f"{srcnf['node']}-{dstnf['node']}-br-0", f"{srcnf['node']}-{dstnf['node']}-0")

        addroutetonfr(data['interfaces'], nfrsrc, nfrdst, srcnf, srcintf, dstnf, dstintf, dstifindex, graph_service_id, g_index, data['location-id'], data['sites'], data['nodes'], tasrc, tadst)

        if srcnf['domain'] == 'external' and srcnf['site'] is None:
          changenfrtogw(nfrsrc)
          addue2smentries(nfrsrc, srcintf, graph_direction, srcnf, srcifindex, dstnf, dstifindex, g_index, graph_service_id, ueids, data['location-id'])
          if not srcnf['predeployed']:
            if not srcnf.get('is-scalable', False):
              addroutetoinit(srcnf, dstnf, dstintf, srcintf, nfrsrc['ip'], afids if graph_direction == 'upstream' else ueids)
            else:
              for i in range(srcnf['instances']):
                if srcnf['static-instance-nodes'][i] == 'external':
                  continue
                if srcnf['static-instance-nodes'][i] == srcnf['node']:
                  addroutetoinit(data['services'][f"{i}--{srcid}"], None, None, f"{srcid}-{i}-br-0", nfrsrc['ip'], afids if graph_direction == 'upstream' else ueids)
                else:
                  ip = str(next(data['macvlan-subnet']))
                  addiptoinit(srcnf, ip, f"{srcid}-{i}-mv-0", None, None)
                  addroutetoinit(data['services'][f"{i}--{srcid}"], None, None, f"{srcid}-{i}-mv-0", ip, afids if graph_direction == 'upstream' else ueids)

        if srcnf.get('is-scalable', False):
          addlb_uplink_entry(srcnf)

    for k, n in data['services'].items():
      #if n['name'] == f'nfrouter-{nfrouter_mode}':
      if k.startswith("nfr-") and not n['predeployed']:
        addcmdtoswitch(n, data['services'], data['interfaces'])
      elif k.startswith("ta-"):
        addcmdtoswitch(n, data['services'], data['interfaces'])
      elif n.get('is-scalable', False):
        addcmdtoswitch(n, data['services'], data['interfaces'])
      elif nf_memif_setup:
        n['cmd'] += 'sleep infinity;'

    if 'macvlan-subnet' in data:
      del data['macvlan-subnet']
    data['unmanaged'] = {}
    cleanintf(data['services'], data['unmanaged'])
    for i in predeployed['interfaces']:
      data['interfaces'].pop(i['id'])

    if 'monitoring-ip' in predeployed:
      data['monitoring-ip'] = predeployed['monitoring-ip']
      data['monitoring-port'] = predeployed['monitoring-port']

    yaml=YAML()
    yaml.width = 4096
    yaml.default_flow_style = False
    yaml.dump(data, f)
    return data

def getListeningPort():
  global predeployed
  return predeployed['listening-port']

def registerToSMO():
  global predeployed
  url = f"http://{predeployed['SMO-ip']}:{predeployed['SMO-port']}/register"
  print(url)
  result = run(['bash', '../utils/allocatable.sh']
    , capture_output = True, text = True)
  b = result
  print(b)
  #try:
  #  x = requests.post(url, json = b)
  #except:
  #  raise Exception(f"SMO error: cant reach server")
  #print('reply:', x.json())

  #if x.status_code != 200:
  #  raise Exception(f"SMO error: {x.json()}")

def getScalablesCurrentInstances(data):
  currInsts = []
  if 'monitoring-ip' in data:
    for s in data['services']:
      if 'parent-instance' in data['services'][s]:
        instId = s.split('--')[0]
        if int(data['services'][data['services'][s]['parent-instance']]['current-instance']) == int(instId):
          currInsts.append(s)
  return currInsts

def startMonitoring(data, nf, ns, podName):
  url = f"http://{data['monitoring-ip']}:{data['monitoring-port']}/Forecasting/activateJob/{data['default-service-id']}/{ns}/{podName}"
  try:
    reply = requests.put(url)
  except:
    raise Exception(f"Monitoring error: cant reach server")
  print('reply:', x.json())
  if x.status_code != 200:
    raise Exception(f"Monitoring error: {x.json()}")
  data['services'][nf]['job-id'] = x

def getNFCPstofill(data):
  need_cp = []
  for s in data['services']:
    if 'entries' in data['services'][s]:
      need_cp.append(s)
  return need_cp

def fillCPofNF(services, nfid, mgmt_ip, mgmt_port=5000):
  print('filing cp of:', nfid)

  for e in services[nfid]['entries']:
    print(e)
    url = f'http://{mgmt_ip}:{mgmt_port}/api/tables/'
    x = requests.post(url, json = e)
    print(x.json())
    if x.status_code != 200:
      raise Exception(f"Controlplane error: {x.json()}")
  print('---')

def determine_nodes(yaml_data):
  patches = []
  if yaml_data['lnsd']['ns-instance-id'] == "55667788": # demo1
    yaml_data['lnsd']['ns']['application-functions'][0]['node'] = 'p42'
    yaml_data['lnsd']['ns']['application-functions'][0]['static-instance-nodes'] = ['orin3', 'ubuntu']
    #patches = ["lnsd.ns.application-functions.[0].node='p42'", "lnsd.ns.application-functions.[0].static-instance-nodes=['orin3', 'ubuntu']"]
  if yaml_data['lnsd']['ns-instance-id'] == "22113344": # demo2
    yaml_data['lnsd']['ns']['application-functions'][0]['node'] = 'xtreme'
    yaml_data['lnsd']['ns']['application-functions'][0]['static-instance-nodes'] = ['xtreme', 'external']
    yaml_data['lnsd']['ns']['network-functions'][0]['node'] = 'xtreme'
    #patches = ["lnsd.ns.application-functions.[0].node='xtreme'", "lnsd.ns.application-functions.[0].static-instance-nodes=['xtreme', 'external']", "lnsd.ns.network-functions.[0].node='xtreme'"]
  #return patch_yaml(f, patches)
  return yaml_data
