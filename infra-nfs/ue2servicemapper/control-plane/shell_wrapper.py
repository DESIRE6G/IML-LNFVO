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
        "attachUE": attachUE,
        "detachUE": detachUE,
        "createService": createService,
        "setHH": setHeavyHitter,
        "unsetHH": notHeavyHitter,
    }
    print("request:", request)
    time.sleep(0.5)
    if request in requestFunctions:
        sh = setupConnection()
        response = requestFunctions[request](sh, parameters)
        teardownConnection(sh)
        return response


def createService(sh, initialParameters):
    print("init:", initialParameters)
    parameters = {
        "table": "ServiceMapper",
        "action": "setD6GService",
        "whatToMatch": ["ig_md.direction", "ig_md.ueid"],
        "value": [str(initialParameters["direction"]), str(initialParameters["UEID"])],
        "paramName": ["serviceId", "nextNF"],
        "actionParam": [
            str(initialParameters["serviceId"]),
            str(initialParameters["nextNF"]),
        ],
    }
    return insertTableEntry(sh, parameters)


def attachUE(sh, initialParameters):
    global UEentries
    print("init:", initialParameters)
    time.sleep(0.5)
    parameters = {
        "table": "UEMapper",
        "action": "UEMapping",
        "whatToMatch": ["ig_md.ueid"],
        "value": [str(initialParameters["UEID"])],
        "paramName": "locationId",
        "actionParam": str(initialParameters["locationID"]),
    }
    result, entry = insertTableEntry(sh, parameters)
    print("inserted entry")
    time.sleep(0.5)
    if result == "OK":
        UEentries[str(initialParameters["UEID"])] = entry
    return result


def detachUE(sh, initialParameters):
    global UEentries
    key = str(initialParameters["UEID"])
    result = "No such entry"
    if key in UEentries:
        UEentries[key].delete()
        del UEentries[key]
        result = "OK"
    return result


def moveUE(sh, initialParameters):
    detachUE(sh, initialParameters)
    return attachUE(sh, initialParameters)


def setHeavyHitter(sh, initialParameters):
    global HHentries
    print("init:", initialParameters)
    parameters = {
        "table": "IsHH",
        "action": "setHH",
        "whatToMatch": ["ig_md.ueid"],
        "value": [str(initialParameters["UEID"])],
    }
    result, entry = insertTableEntry(sh, parameters)
    if result == "OK":
        HHentries[str(initialParameters["UEID"])] = entry
    return result


def notHeavyHitter(sh, initialParameters):
    global HHentries
    key = str(initialParameters["UEID"])
    if key in HHentries:
        HHentries[key].delete()
        del HHentries[key]
    return "OK"


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


def setupConnection(
    grpcAddress="localhost:50051",
    deviceID=0,
    electionID=(0, 1),
    p4infoFile="config/ue2service.p4info.pb.txt",
    binFile="config/ue2service.bin",
):
    sh.setup(
        device_id=deviceID,
        grpc_addr=grpcAddress,
        election_id=electionID,
        config=sh.FwdPipeConfig(p4infoFile, binFile),
    )
    sh.global_options["canonical_bytestrings"] = False
    print("Connected to grpc server")
    return sh
