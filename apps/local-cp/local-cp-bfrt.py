# Python 3.6 compatible
import threading
import queue
import time
import uuid
import signal
import sys
from typing import Optional, Dict, Any, Tuple
from flask import Flask, request, jsonify
import ipaddress
import re

# --- BFRT gRPC client ---
from bfrt_grpc import client as gc

# ============
# CONFIGURATION
# ============

PROGRAM_NAME = "d6ggwv4int"

# Configure your switches here (edit grpc_addr as needed)
GRPC_ADDR="localhost:50052"
SWITCHES = {
    1: {"suffix": "sw1"},
    2: {"suffix": "sw2"},
}

# Mapping short table names to format strings.
# We will fill {suffix} per-switch at runtime.
TABLE_FQN_PATTERNS = {
    "NFRouter":         "NFIngress.nfrouter_{suffix}.NFRouter",
    "NFPortClassifier": "NFIngress.nfrouter_{suffix}.NFPortClassifier",
    "FWDGExecute":      "NFIngress.nfrouter_{suffix}.FWDGExecute",
    "tb_d6gint_handler": "NFIngress.tb_d6gint_handler_{suffix}",
}

# ======================
# BFRT CLIENT BOOTSTRAP
# ======================

class BfrtContext(object):
    def __init__(self, iface, bfrt_info, target):
        self.iface = iface
        self.info = bfrt_info
        self.target = target

def connect_switch(grpc_addr, device_id, client_id=0):
    """
    Create a ClientInterface, fetch BFRT info for PROGRAM_NAME, and a default Target.
    """
    iface = gc.ClientInterface(
        grpc_addr=grpc_addr, client_id=client_id, device_id=device_id
    )
    # Optional but nice: bind the program (SDEs differ; this is safe to call)
    try:
        iface.bind_pipeline_config(PROGRAM_NAME)
    except Exception:
        pass

    bfrt_info = iface.bfrt_info_get(PROGRAM_NAME)
    target = gc.Target(device_id=device_id)
    return BfrtContext(iface, bfrt_info, target)

# Create contexts for all configured switches at import time
SW_CTX = connect_switch( GRPC_ADDR, 0 )

# =======================
# BFRT TABLE OPS (generic)
# =======================

_BFRT_RPC_EXC = getattr(gc, "BfruntimeRpcException", Exception)

def _table_fqn(sw_id, short_name):
    """
    Build fully-qualified table name from short alias (e.g., 'NFRouter').
    """
    if short_name not in TABLE_FQN_PATTERNS:
        raise ValueError("Unknown table short name '{}'".format(short_name))
    suffix = SWITCHES[sw_id]["suffix"]
    return TABLE_FQN_PATTERNS[short_name].format(suffix=suffix)

def _get_table(sw_id, table_short_name):
    ctx = SW_CTX
    fqn = _table_fqn(sw_id, table_short_name)
    try:
        return ctx.info.table_get(fqn)
    except Exception as e:
        raise ValueError("Table '{}' not found (FQN: {}). Error: {}".format(
            table_short_name, fqn, e))

def _resolve_action_name(table, action_short_or_full):
    """
    Accepts a short action ('NFForwardMAC') or full action name.
    Returns the fully-qualified action name as BFRT expects.
    """
    # If caller already gave full name that matches, keep it
    try:
        available = table.info.action_name_list_get() #actions_get()
        # Collect both full names and short suffixes for matching
        full_names = available #[a.name for a in available]
        if action_short_or_full in full_names:
            return action_short_or_full

        # Match by suffix (short)
        for a in available:
            # Many SDEs expose 'NFIngress.nfrouter_sw1.NFForwardMAC' as a.name
            # We consider the last component as the "short" name:
            if a.split(".")[-1] == action_short_or_full: # a.name
                return a # a.name
    except Exception:
        pass
    raise ValueError("Action '{}' not valid for table '{}'. Valid: {}".format(
        action_short_or_full,
        table.info.name_get(),
        [a for a in table.info.action_name_list_get()] #s_get()]
    ))

_MAC_RE = re.compile(r'^[0-9A-Fa-f]{2}([:-])(?:[0-9A-Fa-f]{2}\1){4}[0-9A-Fa-f]{2}$')

def _normalize_value(v):
    """
    Minimal normalizer: keep ints/bytes as-is; leave strings as-is (BFRT can parse hex/dec).
    Extend here if you want dotted IP/MAC parsing like '0x1122..', '10.0.0.1', etc.
    """
    if isinstance(v, (int, bytes)):
        return v

    if isinstance(v, str):
        s = v.strip()

        # Hex literal
        if s.lower().startswith("0x"):
            try:
                return int(s.replace("_", ""), 16)
            except Exception:
                pass

        # IP address (IPv4 or IPv6)
        try:
            ip = ipaddress.ip_address(s)
            return int(ip)
        except ValueError:
            pass

        # MAC address (aa:bb:cc:dd:ee:ff or aa-bb-cc-dd-ee-ff)
        if _MAC_RE.match(s):
            try:
                return int(s.replace(":", "").replace("-", ""), 16)
            except Exception:
                pass

        # Pure decimal string
        if s.isdigit():
            try:
                return int(s)
            except Exception:
                pass

    # Fallback: return as-is (BFRT may accept raw strings for certain fields)
    return v

def full_key_name(table, key_name):
    """
    Map key_name to full table names with control block prefixes
    """
    full_names = table.info.key_field_name_list_get()
    #print(full_names)
    for k in full_names:
        if k.split(".")[-1] == key_name:
            return k
    return key_name


def _make_key(table, match_key):
    """
    Build a BFRT key from a dict:
      - Exact:        field: value
      - LPM:          field: {"value": v, "prefix_len": p}
      - Ternary:      field: {"value": v, "mask": m}
      - Range:        field: {"start": s, "end": e}
      - Optional:     field: {"value": v}
      - Priority:     "$MATCH_PRIORITY": int
    """
    key_tuples = []
    for field_name, spec in match_key.items():
        if field_name == "$MATCH_PRIORITY":
            key_tuples.append(gc.KeyTuple("$MATCH_PRIORITY", int(spec)))
            continue

        field_name = full_key_name(table, field_name)

        if not isinstance(spec, dict):
            key_tuples.append(gc.KeyTuple(field_name, _normalize_value(spec)))
            continue

        if "prefix_len" in spec:
            key_tuples.append(gc.KeyTuple(field_name, _normalize_value(spec["value"]),
                                          prefix_len=int(spec["prefix_len"])))
        elif "mask" in spec:
            key_tuples.append(gc.KeyTuple(field_name, _normalize_value(spec["value"]),
                                          mask=_normalize_value(spec["mask"])))
        elif "start" in spec and "end" in spec:
            key_tuples.append(gc.KeyTuple(field_name, _normalize_value(spec["start"]),
                                          _normalize_value(spec["end"])))
        elif "value" in spec:
            key_tuples.append(gc.KeyTuple(field_name, _normalize_value(spec["value"])))
        else:
            raise ValueError("Unrecognized match spec for '{}': {}".format(field_name, spec))
    return table.make_key(key_tuples)

def _make_data(table, action_name_full, action_params):
    tuples = [gc.DataTuple(k, _normalize_value(v)) for k, v in action_params.items()]
    return table.make_data(tuples, action_name=action_name_full)

def insertTableEntry(sw_id, parameters):
    """
    Insert a table entry via bfrt_grpc (standalone Python).
    Request schema:
      parameters = {
        "table": "NFRouter",                 # short table alias (mapped to FQN)
        "action": "NFForwardMAC",            # short or full action name
        "keys": {...},                       # match fields (see _make_key)
        "actionParameters": {...}            # action params
      }
    """
    table_short = parameters["table"]
    action_any  = parameters["action"]
    keys        = parameters.get("keys", {}) or {}
    act_params  = parameters.get("actionParameters", {}) or {}

    table = _get_table(sw_id, table_short)
    action_full = _resolve_action_name(table, action_any)

    key = _make_key(table, keys)
    data = _make_data(table, action_full, act_params)

    ctx = SW_CTX
    try:
        table.entry_add(ctx.target, [key], [data])
    except _BFRT_RPC_EXC:
        # If exists, modify it
        table.entry_mod(ctx.target, [key], [data])

    return "OK"

def setup_mirroring(sid, port):
    mirror_table = SW_CTX.info.table_get("$mirror.cfg")
    target = SW_CTX.target

    key = mirror_table.make_key([
        gc.KeyTuple("$sid", sid)
    ])

    data = mirror_table.make_data(
    [
        gc.DataTuple("$direction", str_val = "INGRESS"),
        gc.DataTuple("$session_enable", bool_val = True),
        gc.DataTuple("$ucast_egress_port", port),
        gc.DataTuple("$ucast_egress_port_valid", bool_val = True),
        gc.DataTuple("$max_pkt_len", 43),
    ],
    action_name="$normal"
    )

    # Add (or modify if exists)
    try:
        mirror_table.entry_add(target, [key], [data])
        print("[OK] mirror.cfg entry added")
    except gc.BfruntimeRpcException:
        mirror_table.entry_mod(target, [key], [data])
        print("[OK] mirror.cfg entry modified")

    # -----------------------
    # Dump table contents
    # -----------------------
    print("\nCurrent mirror.cfg entries:")
    entries = mirror_table.entry_get(target, [], {"from_hw": False})

    for data_obj, key_obj in entries:
        kdict = key_obj.to_dict()
        ddict = data_obj.to_dict()
        key_dict = {"$sid": kdict["$sid"]["value"]}
        data_dict = {}
        for field in ["$direction", "$session_enable", "$ucast_egress_port", "$ucast_egress_port_valid", "$max_pkt_len"]:
            try:
                data_dict[field] = ddict[field]
            except Exception:
                pass
        print("Key:", key_dict, "->", data_dict)

# ==============
# REQUEST ENGINE
# ==============

def processRequest(request_name, parameters, sw_id):
    requestFunctions = {
        "insertTableEntry": insertTableEntry,
        # you can add: "clearTable": clearTable, "getTableEntries": getTableEntries, etc.
    }
    if request_name in requestFunctions:
        return requestFunctions[request_name](sw_id, parameters)
    return "Unknown request '{}'".format(request_name)

def response_generator(requestQueue, responseData, exit_signal):
    while not exit_signal.is_set():
        if not requestQueue.empty():
            request_item = requestQueue.get()
            request_payload, token, sw_id = request_item
            try:
                response = processRequest(request_payload[0], request_payload[1], sw_id)
            except Exception as ex:
                response = "Exception: {}".format(ex)
            if response is None:
                response = "Can't interpret request"
            responseData[token] = response
        time.sleep(0.05)

# =========
# FLASK APPS for emulating the two switches on a single Tofino
# =========

app_sw1 = Flask("switch-lcp-1")

@app_sw1.errorhandler(Exception)
def handle_error1(error):
    response = jsonify("Error: {}".format(error))
    response.status_code = 500
    return response

@app_sw1.route("/api/tables/", methods=["POST"])
def insert_into_table_request1():
    requestData = request.get_json(force=True) or {}
    token = str(uuid.uuid4())

    # Choose switch; allow client to pass sw_id in JSON, default=1
    sw_id = 1 #int(requestData.get("sw_id", 1))

    data = ["insertTableEntry", requestData]
    requestQueue.put((data, token, sw_id))
    # Simple wait loop (your original approach)
    while True:
        if token in responseData:
            response = responseData.pop(token)
            return jsonify({"response": response}), 200
        time.sleep(0.05)

app_sw2 = Flask("switch-lcp-2")

@app_sw2.errorhandler(Exception)
def handle_error2(error):
    response = jsonify("Error: {}".format(error))
    response.status_code = 500
    return response

@app_sw2.route("/api/tables/", methods=["POST"])
def insert_into_table_request2():
    requestData = request.get_json(force=True) or {}
    token = str(uuid.uuid4())

    # Choose switch; allow client to pass sw_id in JSON, default=1
    sw_id = 2 #int(requestData.get("sw_id", 1))

    data = ["insertTableEntry", requestData]
    requestQueue.put((data, token, sw_id))
    # Simple wait loop (your original approach)
    while True:
        if token in responseData:
            response = responseData.pop(token)
            return jsonify({"response": response}), 200
        time.sleep(0.05)

def run_app_sw1():
    app_sw1.run(host="0.0.0.0", port=5555, debug=False, use_reloader=False)

def run_app_sw2():
    app_sw2.run(host="0.0.0.0", port=5556, debug=False, use_reloader=False)


# ===============
# THREAD BOOTSTRAP
# ===============

requestQueue = queue.Queue()
responseData = {}

exit_signal = threading.Event()
response_thread = threading.Thread(
    target=response_generator, args=(requestQueue, responseData, exit_signal)
)
response_thread.daemon = True
response_thread.start()

# Graceful shutdown to close interfaces
def _shutdown(signum=None, frame=None):
    try:
        exit_signal.set()
        time.sleep(0.1)
    finally:
        # Close all BFRT interfaces
        try:
            SW_CTX.iface._tear_down_stream()  # best-effort; older SDEs
        except Exception:
            pass
    sys.exit(0)

signal.signal(signal.SIGINT, _shutdown)
signal.signal(signal.SIGTERM, _shutdown)

# ======
# MAIN
# ======
import traceback
if __name__ == "__main__":
    try:
        setup_mirroring(sid=100, port=16)
        time.sleep(1.0)
        t1 = threading.Thread(target=run_app_sw1)
        t2 = threading.Thread(target=run_app_sw2)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
    except Exception as ex:
        print("Exception:")
        print(ex)
    traceback.print_exc()

