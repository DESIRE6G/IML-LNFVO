import p4runtime_sh.shell as sh
from p4runtime_sh.context import P4Type, P4RuntimeEntity
import time

def processRequest(request, parameters):
    requestFunctions = {
        "getTableEntries": getTableEntries,
        "clearTable": clearTable,
        "insertTableEntry": insertTableEntry,
    }
    if request in requestFunctions:
        sh = setupConnection()
        response = requestFunctions[request](sh, parameters)
        teardownConnection(sh)
        return response

def clearTable(sh, tableName):
    table = sh.TableEntry(tableName)
    table.read(function=lambda x: x.delete())
    return "OK"

def insertTableEntry(sh, parameters):
    te = sh.TableEntry(parameters["table"])(action=parameters["action"])

    for k, v in parameters["keys"].items():
      te.match[k] = str(v)

    if 'priority' in parameters["parameters"]:
        te.priority = priority

    for k, v in parameters["actionParameters"].items():
      te.action[k] = str(v)

    # TODO use proper exception
    try:
      te.insert()
    except:
      te.modify()
    return "OK"

def getTableEntries(sh, tableName):
    entries = []
    table = sh.TableEntry(tableName)
    for te in table.read():
        entries.append(str(te))
    return entries

def teardownConnection(sh):
    sh.teardown()

def uploadDP(
    p4infoPath,
    binPath,
    grpcAddress="localhost:50051",
    deviceID=1,
    electionID=(0, 1),
):
    sh.setup(
        device_id=deviceID,
        grpc_addr=grpcAddress,
        election_id=electionID,
        config=sh.FwdPipeConfig(p4infoPath, binPath),
    )
    sh.teardown()

def setupConnection(
    grpcAddress="localhost:50051",
    deviceID=1,
    electionID=(0, 1)
):
    sh.setup(
        device_id=deviceID,
        grpc_addr=grpcAddress,
        election_id=electionID,
    )
    sh.global_options["canonical_bytestrings"] = False
    print("Connected to grpc server")
    return sh
