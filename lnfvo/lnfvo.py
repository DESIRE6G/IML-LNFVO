import os
import traceback
import sys
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import SingleQuotedScalarString,DoubleQuotedScalarString
import random
import requests
import time

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
  d = next(i for i in dstnf['interfaces'] if i['interface'] == dstintf)
  if 'memifid' in s and nf_memif_setup:
    srcnf["cmd"] += f"vppctl \"set ip neighbor memif{s['memifid']+1}/{s['memifid']} {d['ip']} {d['mac']}\";"
    srcnf["cmd"] += f"vppctl \"ip route add {d['ip']}/32 via memif{s['memifid']+1}/{s['memifid']}\";"
    srcnf["cmd"] = SingleQuotedScalarString(srcnf["cmd"])
  elif 'memifid' not in s:
    dstip = afids[0]
    srcnf['env']['AF_IP'] = dstip
    srcnf["initcmd"] += f"ip route add {d6g_gw}/32 dev {srcintf};ip route add {dstip}/32 via {d6g_gw} dev {srcintf};"
    srcnf["initcmd"] = SingleQuotedScalarString(srcnf["initcmd"])

def addif(dic, name, type, ifindex=None):
  if f"{name}-{type}-{ifindex}" in dic:
    return
  n = {}
  n["type"] = type
  if type == "sriov":
    n["mac"] = SingleQuotedScalarString(generate_mac())
    n["vf"] = SingleQuotedScalarString("nvidia.com/cx6dx_vf")
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

def addtonf(nf, name, intf, macs=None, ips=None, ifindex=None, g_index=None, memifid=None):
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
  if macs is not None:
    if ifindex not in macs:
      macs[ifindex] = generate_mac()
    i['mac'] = SingleQuotedScalarString(macs[ifindex])
  if ips is not None:
    if ifindex not in ips:
      ips[ifindex] = generate_ip()
    i['ip'] = ips[ifindex]
    addiptoinit(nf, ips[ifindex], intf, memifid, macs[ifindex])
  nf['interfaces'].append(i)

def addroutetonfr(infs, nfrsrc, nfrdst, srcnf, srcintfname, dstnf, dstintfname, serviceid, g_index, l_index, locationId):
  nfrdstport = getifindex(nfrdst, dstintfname)
  nfrsrcport = getifindex(nfrsrc, srcintfname)
  srcintf = getif(srcnf, srcintfname)
  dstintf = getif(dstnf, dstintfname)
  srcport = str(getifindex(srcnf, srcintfname))
  dstport = str(getifindex(dstnf, dstintfname))

  if nfrouter_mode == 'dpdk':
    nfrdst['files']['ipv4rules.cfg'] += f"R{dstintf['ip']}/32 {nfrdstport}\n"
    if srcnf['node'] != dstnf['node']:
      port = getifindex(nfrsrc, f"{srcnf['node']}-{dstnf['node']}-1")
      nfrsrc['files']['ipv4rules.cfg'] += f"R{dstintf['ip']}/32 {port}\n"
  elif nfrouter_mode == 't4p4s' or nfrouter_mode == 'bmv2':

    # TODO refactor to if link is not from external?
    if l_index != 0:
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
    if dstnf['domain'] == 'internal':
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
            "srcMAC": nfrsrc['mac'],
            "dstMAC": dstintf['mac']
            }
          }
      addcpentry(nfrdst['entries'], entry)
    elif dstnf['domain'] == 'external':
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
            "srcMAC": nfrsrc['mac'], # or nfrsrc sriov's MAC
            "dstMAC": dstintf['mac']
            }
          }
      addcpentry(nfrdst['entries'], entry)
    if srcnf['node'] != dstnf['node']:
      ifname = f"{srcnf['node']}-{dstnf['node']}-1"
      port = getifindex(nfrsrc, ifname)

      #dstifname = f"{dstnf['node']}-{srcnf['node']}-1"
      #name = getif(nfrdst, dstifname)['name']
      dstifname = f"{dstnf['node']}-sriov-1"

      # TODO srcMAC should be this?
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
            "dstMAC": infs[dstifname]['mac']
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
  infranf_name = 'd6g-gw-v4'
  result = run(['make', '-C', './infra-nfs', infranf_name], capture_output = True, text = True)
  nfr['files'] = [
      {"name": f"{infranf_name}.p4info.txtpb", "path": f"../../infra-nfs/{infranf_name}/data-plane/{infranf_name}.p4info.txtpb"},
      {"name": f"{infranf_name}.json", "path": f"../../infra-nfs/{infranf_name}/data-plane/{infranf_name}.json"}
  ]
  nfr['cmd'] = f'/p4runtime-sh/venv/bin/python  /local-cp/local-cp.py /opt/nfconfig/{nfr["files"][0]["name"]} /opt/nfconfig/{nfr["files"][1]["name"]}'
  #nfr['cmd'] = 'trap : TERM INT; sleep infinity & wait'
def addnfr(services, node, infranfs):
  if f"nfr-{node}" in services:
    return
  d = {}
  d['name'] = f'simple-switch-{nfrouter_mode}'
  d['node'] = node
  d['mac'] = generate_mac()
  if infranfs:
    nfr = next((i for i in infranfs if i['instance-id'] == f"nfr-{node}"), None)
    if nfr:
      d['mac'] = nfr['static-mac']
      d['ip'] = nfr['static-ip']

  d['is_edge'] = False
  if nfrouter_mode == 'dpdk':
    d['files'] = {}
    d['files']['ipv6rules.cfg'] = SingleQuotedScalarString('R::/128 0')
    d['files']['ipv4rules.cfg'] = ''
  elif nfrouter_mode == 't4p4s':
    d['sidecar'] = {}
    d['sidecar']['image'] = 'desire6g/nfrouter-t4p4s:latest'
    d['sidecar']['cmd'] = '/root/t4p4s/examples/nfr-controlplane/venv/bin/python3 /root/t4p4s/examples/nfr-controlplane/nfr-cp.py'
  elif nfrouter_mode == 'bmv2':

    infranf_name = 'nfrouter'
    result = run(['make', '-C', './infra-nfs', infranf_name], capture_output = True, text = True)
    d['files'] = [
        {"name": f"{infranf_name}.p4info.txtpb", "path": f"../../infra-nfs/{infranf_name}/data-plane/{infranf_name}.p4info.txtpb"},
        {"name": f"{infranf_name}.json", "path": f"../../infra-nfs/{infranf_name}/data-plane/{infranf_name}.json"}
    ]

    d['entries'] = []
    d['image'] = 'desire6g/local-cp:latest'
    d['cmd'] = f'/p4runtime-sh/venv/bin/python  /local-cp/local-cp.py /opt/nfconfig/{d["files"][0]["name"]} /opt/nfconfig/{d["files"][1]["name"]}'
    #d['cmd'] = 'trap : TERM INT; sleep infinity & wait'

  services[f"nfr-{node}"] = d

def addcpentry(entries, entry):
  if entry not in entries:
    entries.append(entry)

def addcmdtonfr(nfr, services, interfaces, is_edge):
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
  if nfrouter_mode == 'dpdk':
    cmdopts += ' --mode=poll -P'

  if nfrouter_mode == 'dpdk':
    i = 0
    for intf in nfr['interfaces']:
      servicewithtype, ifindex = intf['name'].rsplit('-', 1)
      service, type = servicewithtype.rsplit('-', 1)
      if type == 'br' or type == 'memif':
        mac = getif(services[service], intf['name'])['mac']
      elif type == 'sriov':
        _if = intf['interface'].rsplit('-', 1)[0]
        mac = interfaces[f"{_if.rsplit('-', 1)[1]}-sriov-1"]['mac']
      cmdopts += f" --eth-dest={i},{mac}"
      i += 1
    cmdopts += ' --rule_ipv4="/opt/nfconfig/ipv4rules.cfg" --rule_ipv6="/opt/nfconfig/ipv6rules.cfg"'

  if anymemif and nfrouter_mode == 'dpdk':
    cmdopts += ' --relax-rx-offload --parse-ptype'

  if nfrouter_mode == 'dpdk':
    nfr['cmd'] = SingleQuotedScalarString(f'./l3fwd-static {ealopts} -- {cmdopts}')
  elif nfrouter_mode == 't4p4s':
    nfr['cmd'] = SingleQuotedScalarString(f'echo "nfroutereal -> ealopts += { ealopts }" >> /root/t4p4s/opts_dpdk.cfg;echo "nfrouterports -> cmdopts += { cmdopts }" >> /root/t4p4s/opts_dpdk.cfg;P4PI=/root/t4p4s/third_party/PI GRPCPP=/root/t4p4s/third_party/P4Runtime_GRPCPP GRPC=/root/t4p4s/third_party/grpc PYTHON3=/root/t4p4s/.venv/bin/python /root/t4p4s/t4p4s.sh :nfrouter p4rt dbg verbose')
  elif nfrouter_mode == 'bmv2':
    nfr['sidecar'] = {}
    nfr['sidecar']['image'] = 'desire6g/simple-switch-bmv2:latest'
    nfr['sidecar']['cmd'] = SingleQuotedScalarString(f'simple_switch_grpc --log-console --device-id 1 {bmv2opts} /opt/nfconfig/{nfr["files"][1]["name"]} -- --grpc-server-addr 0.0.0.0:50051')
    #nfr['sidecar']['cmd'] = SingleQuotedScalarString('trap : TERM INT; sleep infinity & wait')

def cleanintf(services):
  for s in list(services):
    for i in services[s]['interfaces']:
      if 'ip' in i:
        del i['ip']
      if 'memifid' in i:
        del i['mac']
        del i['memifid']
    if services[s]['name'] == 'unmanaged':
      del services[s]

def encodenfidport(nfid: int, port: int):
  return (nfid << 8) + port

def addnf(services, nf, domain, gs, name=None, node=None, siteId=None):
  s = {}
  s['name'] = nf['id'] if name is None else name
  s['node'] = nf['node'] if node is None else node
  s['site'] = siteId
  s['domain'] = domain
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
  if s['domain'] == 'external':
    #s['ips'] = {}
    if 'static-ips' in nf:
      for idx, val in enumerate(nf['static-ips']):
        given_ips.append(val)
        s['ips'][str(idx)] = val

  s['interfaces'] = []
  s['is-ue'] = nf.get('is-ue', False)
  s['env'] = {}
  services[nf['instance-id']] = s

predeployed = {}
def parse_siteconfig(path):
  pd = {}
  if not os.path.isfile(path):
    pd['predeployed-afs'] = []
    return pd

  with open(path, 'r') as f:
    try:
      yaml=YAML(typ='safe')
      sconfig = yaml.load(f)
      pd['predeployed-afs'] = sconfig['predeployed-afs']
      return pd

    except Exception as ex:
      response = (f'{type(ex).__name__}: {ex.args}', 500)
      traceback.print_exc()

def addue2smentries(nfrsrc, srcintf, graph_direction, srcnf, srcifindex, dstnf, dstifindex, g_index, graph_service_id, ueids, location_id):
  # TODO this should be done with external -> external?
  nfrsrcport = getifindex(nfrsrc, srcintf)

  entry = {
      "table": "ModeSelector",
      "action": "setUpstreamMode4" if graph_direction == 'upstream' else "setDownstreamMode4",
      "keys": {"ingress_port": nfrsrcport},
      "actionParameters": {}
      }
  addcpentry(nfrsrc['entries'], entry)

  relevantues = [srcnf['ips'][srcifindex]] if graph_direction == 'upstream' and srcnf['is-ue'] else ueids
  #relevantues = [srcnf['ips'][srcifindex]] if graph_direction == 'upstream' and srcnf['is-ue'] else [dstnf['ips'][dstifindex]]
  #print(relevantues)
  #print(dstnf['ips'][dstifindex])
  for ueid in relevantues:
    smentry = {
        "table": "ServiceMapper",
        "action": "setD6GService",
        "keys": {
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
  site = {}
  site['srcmac'] = s['srcmac']
  site['dstmac'] = s['dstmac']
  site['srcip'] = s['srcip']
  site['dstip'] = s['dstip']
  site['nfr-mac'] = s['nfr-mac']
  site['transport-type'] = s['transport-type']
  site['transport-node'] = s['transport-node']
  data['sites'][s['id']] = site

def getueidsofgraph(links, graph_direction, services, afs):
  ueids = []
  afids = []
  for l in links:
    if graph_direction == 'upstream':
      nfid, nfifidx = l['connection-points'][0]['if-id-ref'].split(':')
      afid, afifidx = l['connection-points'][1]['if-id-ref'].split(':')
    else:
      afid, afifidx = l['connection-points'][0]['if-id-ref'].split(':')
      nfid, nfifidx = l['connection-points'][1]['if-id-ref'].split(':')
    nf = services[nfid]
    af = services[afid]
    # TODO handle s2s connections
    if nf['is-ue']:
      if nfifidx not in nf['ips']:
        nf['ips'][nfifidx] = generate_ip()
      ueids.append(nf['ips'][nfifidx])

    anyaf = False
    for i in afs:
      if af['name'] == i['id']:
        anyaf = True
        break
    if anyaf:
      if afifidx not in af['ips']:
        af['ips'][afifidx] = generate_ip()
      afids.append(af['ips'][afifidx])
  return ueids, afids

def addmemifmount(nf, srcid):
  nf['hostpath'] = {'name': 'shared-dir', 'hostpath': f"/run/vpp/{srcid}", 'path': "/var/lib/cni/usrspcni"}

def generate_values(nsd, path):
  global predeployed
  global nfrouter_mode
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

    for i in nsd['lnsd']['ns']['network-functions']:
      addnf(data['services'], i, 'internal', gs)

    for i in nsd['lnsd']['ns']['application-functions']:
      addnf(data['services'], i, i['domain'], gs)

    for i in predeployed['predeployed-afs']:
      addnf(data['services'], i, i['domain'], gs, 'unmanaged')

    for s in nsd['lnsd']['ns']['site-connections']:
      addsite(data['sites'], s)
      for i in s['network-functions']:
        addnf(data['services'], i, 'internal', gs, 'unmanaged', s['transport-node'], s['id'])
      for i in s['application-functions']:
        addnf(data['services'], i, i['domain'], gs, 'unmanaged', s['transport-node'], s['id'])

    for g_index, g in enumerate(nsd['lnsd']['ns']['forwarding_graphs']):
      nfrouter_mode = g.get('nfrouter-mode', data['default-nfr-mode'])
      graph_direction = g['direction']
      graph_service_id = g.get('service-id', data['default-service-id'])

      ueids, afids = getueidsofgraph(g['links'], graph_direction, data['services'], nsd['lnsd']['ns']['application-functions'])

      for l_index, l in enumerate(g['links']):
        interpod_mode = l.get("interpod-mode", data['default-interpod-mode'])

        srcid, srcifindex = l['connection-points'][0]['if-id-ref'].split(':')
        dstid, dstifindex = l['connection-points'][1]['if-id-ref'].split(':')

        srcnf = data['services'][srcid]
        dstnf = data['services'][dstid]

        addif(data['interfaces'], srcid, interpod_mode, srcifindex)
        addif(data['interfaces'], dstid, interpod_mode, dstifindex)
        srcintf = f'{srcid}-{interpod_mode}-{srcifindex}'
        dstintf = f'{dstid}-{interpod_mode}-{dstifindex}'
        addtonf(srcnf, srcintf, srcintf, srcnf['macs'], srcnf['ips'], srcifindex, g_index, getnextmemifid(srcid) if interpod_mode == 'memif' else None)
        addtonf(dstnf, dstintf, dstintf, dstnf['macs'], dstnf['ips'], dstifindex, g_index, getnextmemifid(dstid) if interpod_mode == 'memif' else None)

        addnfr(data['services'], srcnf['node'], nsd['lnsd']['ns'].get('infra-nfs'))
        addnfr(data['services'], dstnf['node'], nsd['lnsd']['ns'].get('infra-nfs'))

        nfrsrc = data['services'][f"nfr-{srcnf['node']}"]
        nfrdst = data['services'][f"nfr-{dstnf['node']}"]

        # TODO refactor into addnfr and addtonf or addif?
        if interpod_mode == 'memif':
          addmemifmount(srcnf, srcid)
          addmemifmount(dstnf, srcid)
          addmemifmount(nfrsrc, srcid)
          addmemifmount(nfrdst, srcid)

        addtonf(nfrsrc, srcintf, srcintf)
        addtonf(nfrdst, dstintf, dstintf)

        if srcnf['node'] != dstnf['node']:
          addif(data['interfaces'], srcnf['node'], "sriov", 1)
          addif(data['interfaces'], dstnf['node'], "sriov", 1)
          addtonf(nfrsrc, f"{srcnf['node']}-sriov-1", f"{srcnf['node']}-{dstnf['node']}-1")

        addroutetonfr(data['interfaces'], nfrsrc, nfrdst, srcnf, srcintf, dstnf, dstintf, graph_service_id, g_index, l_index, data['location-id'])

        #if srcnf['domain'] == 'external' and dstnf['domain'] == 'internal':
        if srcnf['domain'] == 'external':
          changenfrtogw(nfrsrc)
          addue2smentries(nfrsrc, srcintf, graph_direction, srcnf, srcifindex, dstnf, dstifindex, g_index, graph_service_id, ueids, data['location-id'])
          addroutetoinit(srcnf, dstnf, dstintf, srcintf, nfrsrc['ip'], afids if graph_direction == 'upstream' else ueids)

    for k, n in data['services'].items():
      #if n['name'] == f'nfrouter-{nfrouter_mode}':
      if k.startswith("nfr-"):
        addcmdtonfr(n, data['services'], data['interfaces'], n['is_edge'])
      elif nf_memif_setup:
        n['cmd'] += 'sleep infinity;'

    cleanintf(data['services'])
    yaml=YAML()
    yaml.width = 4096
    yaml.default_flow_style = False
    #generate_end = time.time()
    #print(f"time to generate values.yaml in mem: {generate_end - generate_start}")
    #dump_start = time.time()
    yaml.dump(data, f)
    #dump_end = time.time()
    #print(f"time to dump values.yaml: {dump_end - dump_start}")
    #print(data)
    return data

def getNFCPstofill(data):
  need_cp = []
  for s in data['services']:
    if 'entries' in data['services'][s]:
      need_cp.append(s)
  return need_cp

def fillCPofNF(data, nfid, mgmt_ip, mgmt_port=5000):
  print(nfid)

  for e in data['services'][nfid]['entries']:
    print(e)
    url = f'http://{mgmt_ip}:{mgmt_port}/api/tables/'
    x = requests.post(url, json = e)
    print(x.json())
    if x.status_code != 200:
      raise Exception(f"Controlplane error: {x.json()}")
  print('---')
