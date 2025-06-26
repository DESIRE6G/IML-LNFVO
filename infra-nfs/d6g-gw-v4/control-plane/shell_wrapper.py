import p4runtime_sh.shell as sh
from p4runtime_sh.context import P4Type, P4RuntimeEntity
import time

global tableEntries
tableEntries = {}
global UEentries
UEentries = {}

def processRequest(request, parameters):
    requestFunctions = {
        "getTable": getTables,
        "clearTable": clearTable,
        "insertIntoTable": insertTableEntry,
        "NFPortClassifier": NFPortClassifier,
        "FWDGExecute": FWDGExecute,
        "NFForward": NFForward,
        "NFForwardMAC": NFForwardMAC,
        "NFForwardExternal": NFForwardExternal,
        "setDownstreamMode4": setDownstreamMode4,
        "setUpstreamMode4": setUpstreamMode4,
        "setD6GService": setD6GService,
        "UEMapping": UEMapping,
        "arp_reply": arp_reply,
        "icmp_reply": icmp_reply
    }
    print("request:", request)
    time.sleep(0.1)
    if request in requestFunctions:
        sh = setupConnection()
        response = requestFunctions[request](sh, parameters)
        teardownConnection(sh)
        return response

def NFPortClassifier(sh, initialParameters):
    print("init:", initialParameters)
    parameters = {
        "table": "NFPortClassifier",
        "action": "NoAction",
        "whatToMatch": ["standard_metadata.ingress_port"],
        "value": [str(initialParameters["ingress_port"])],
        "paramName": [],
        "actionParam": [],
    }
    result, entry = insertTableEntry(sh, parameters)
    return result

def FWDGExecute(sh, initialParameters):
    print("init:", initialParameters)
    parameters = {
        "table": "FWDGExecute",
        "action": "UpdateNF",
        "whatToMatch": ["hdr.d6gmain.serviceId", "hdr.d6gmain.nextNF"],
        "value": [str(initialParameters["serviceId"]), str(initialParameters["nextNF"])],
        "paramName": ["nfid"],
        "actionParam": [str(initialParameters["nfid"])],
    }
    result, entry = insertTableEntry(sh, parameters)
    return result

def NFForward(sh, initialParameters):
    print("init:", initialParameters)
    parameters = {
        "table": "NFRouter",
        "action": "NFForward",
        "whatToMatch": ["hdr.d6gmain.serviceId", "hdr.d6gmain.locationId", "hdr.d6gmain.nextNF"],
        "value": [str(initialParameters["serviceId"]), str(initialParameters["locationId"]), str(initialParameters["nextNF"]) ],
        "paramName": ["port"],
        "actionParam": [str(initialParameters["port"])],
    }
    result, entry = insertTableEntry(sh, parameters)
    return result

def NFForwardMAC(sh, initialParameters):
    print("init:", initialParameters)
    parameters = {
        "table": "NFRouter",
        "action": "NFForwardMAC",
        "whatToMatch": ["hdr.d6gmain.serviceId", "hdr.d6gmain.locationId", "hdr.d6gmain.nextNF"],
        "value": [str(initialParameters["serviceId"]), str(initialParameters["locationId"]), str(initialParameters["nextNF"]) ],
        "paramName": ["port", "srcMAC", "dstMAC"],
        "actionParam": [str(initialParameters["port"]), str(initialParameters["srcMAC"]), str(initialParameters["dstMAC"])],
    }
    result, entry = insertTableEntry(sh, parameters)
    return result

def NFForwardExternal(sh, initialParameters):
    print("init:", initialParameters)
    parameters = {
        "table": "NFRouter",
        "action": "NFForwardToExternal",
        "whatToMatch": ["hdr.d6gmain.serviceId", "hdr.d6gmain.locationId", "hdr.d6gmain.nextNF"],
        "value": [str(initialParameters["serviceId"]), str(initialParameters["locationId"]), str(initialParameters["nextNF"])],
        "paramName": ["port", "srcMAC", "dstMAC"],
        "actionParam": [str(initialParameters["port"]), str(initialParameters["srcMAC"]), str(initialParameters["dstMAC"])],
    }
    result, entry = insertTableEntry(sh, parameters)
    return result

def setDownstreamMode4(sh, initialParameters):
    print("init:", initialParameters)
    parameters = {
        "table": "ModeSelector",
        "action": "setDownstreamMode4",
        #"whatToMatch": ["standard_metadata.ingress_port", "hdr.ipv4.isValid()"],
        #"value": [str(initialParameters["ingress_port"]), str(initialParameters["ipv4validity"])],
        "whatToMatch": ["standard_metadata.ingress_port"],
        "value": [str(initialParameters["ingress_port"])],
        #"paramName": ["port"],
        #"actionParam": [str(initialParameters["port"])],
        "paramName": [],
        "actionParam": [],
    }
    result, entry = insertTableEntry(sh, parameters)
    return result

def setUpstreamMode4(sh, initialParameters):
    print("init:", initialParameters)
    parameters = {
        "table": "ModeSelector",
        "action": "setUpstreamMode4",
        #"whatToMatch": ["standard_metadata.ingress_port", "hdr.ipv4.isValid()"],
        #"value": [str(initialParameters["ingress_port"]), str(initialParameters["ipv4validity"])],
        "whatToMatch": ["standard_metadata.ingress_port"],
        "value": [str(initialParameters["ingress_port"])],
        #"paramName": ["port"],
        #"actionParam": [str(initialParameters["egress_port"])],
        "paramName": [],
        "actionParam": [],
    }
    result, entry = insertTableEntry(sh, parameters)
    return result

def setD6GService(sh, initialParameters):
    print("init:", initialParameters)
    parameters = {
        "table": "ServiceMapper",
        "action": "setD6GService",
        "whatToMatch": ["ig_md.direction", "ig_md.ueid"],
        "value": [str(initialParameters["direction"]), str(initialParameters["ueid"])],
        "paramName": ["serviceId", "nextNF"],
        "actionParam": [str(initialParameters["serviceId"]), str(initialParameters["nextNF"])],
    }
    result, entry = insertTableEntry(sh, parameters)
    return result

def UEMapping(sh, initialParameters):
    print("init:", initialParameters)
    parameters = {
        "table": "UEMapper",
        "action": "UEMapping",
        "whatToMatch": ["ig_md.ueid"],
        "value": [str(initialParameters["ueid"])],
        "paramName": ["locationId"],
        "actionParam": [str(initialParameters["locationId"])],
    }
    result, entry = insertTableEntry(sh, parameters)
    return result

def arp_reply(sh, initialParameters):
    print("init:", initialParameters)
    parameters = {
        "table": "arp_responder_v4",
        "action": "arp_reply",
        "whatToMatch": ["hdr.arp.oper", "hdr.arp_ipv4.tpa"],
        "value": [str(initialParameters["arp_oper"]), str(initialParameters["arp_tpa"])],
        "paramName": ["my_mac"],
        "actionParam": [str(initialParameters["my_mac"])],
    }
    result, entry = insertTableEntry(sh, parameters)
    return result

def icmp_reply(sh, initialParameters):
    print("init:", initialParameters)
    parameters = {
        "table": "icmp_responder_v4",
        "action": "icmp_reply",
        "whatToMatch": ["hdr.ethernet.dstAddr", "hdr.ipv4.dstAddr"],
        "value": [str(initialParameters["macdst"]), str(initialParameters["ipdst"])],
        "paramName": [],
        "actionParam": [],
    }
    result, entry = insertTableEntry(sh, parameters)
    return result

def clearTable(tableName):
    if tableName != "":
        if tableName in tableEntries:
            for entry in tableEntries[tableName]:
                entry.delete()
            tableEntries[tableName] = []
        else:
            return None
        return "OK"
    else:
        return clearAllTables()

def clearAllTables():
    for tableName in tableEntries:
        clearTable(tableName)
    return "OK"

def insertTableEntry(sh, parameters):
    global tableEntries
    te = sh.TableEntry(parameters["table"])(action=parameters["action"])
    if type(parameters["whatToMatch"]) == list:
        i = 0
        while i < len(parameters["whatToMatch"]):
            te.match[parameters["whatToMatch"][i]] = parameters["value"][i]
            i += 1
    if type(parameters["paramName"]) == list:
        i = 0
        while i < len(parameters["paramName"]):
            te.action[parameters["paramName"][i]] = parameters["actionParam"][i]
            i += 1
    te.insert()
    if parameters["table"] in tableEntries:
        tableEntries[parameters["table"]].append(te)
    else:
        tableEntries[parameters["table"]] = [te]
    return "OK", te

def getTables(sh, tableName):
    if tableName == "":
        tableList = []
        for table in sh.P4Objects(P4Type.table):
            tableList.append(str(table))
        return tableList
    else:
        return getTable(sh, tableName)

def getTable(sh, tableName):
    if tableName in sh.P4Objects(P4Type.table):
        return str(sh.P4Objects(P4Type.table)[tableName])
    return None

def teardownConnection(sh):
    sh.teardown()

def uploadDP(
    grpcAddress="localhost:50051",
    deviceID=1,
    electionID=(0, 1),
    p4infoFile="d6g-gw-v4.p4runtime.txt",
    binFile="../data-plane/d6g-gw-v4.json",
):
    sh.setup(
        device_id=deviceID,
        grpc_addr=grpcAddress,
        election_id=electionID,
        config=sh.FwdPipeConfig(p4infoFile, binFile),
    )
    sh.teardown()

def setupConnection(
    grpcAddress="localhost:50051",
    deviceID=1,
    electionID=(0, 1),
    p4infoFile="d6g-gw-v4.p4runtime.txt",
    binFile="../data-plane/d6g-gw-v4.json",
):
    sh.setup(
        device_id=deviceID,
        grpc_addr=grpcAddress,
        election_id=electionID,
        #config=sh.FwdPipeConfig(p4infoFile, binFile),
    )
    sh.global_options["canonical_bytestrings"] = False
    print("Connected to grpc server")
    return sh
