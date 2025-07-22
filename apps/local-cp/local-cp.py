import threading
import queue
import time
import uuid
import signal
import sys
import shell_wrapper as sw
from flask import Flask, request, jsonify

app = Flask(__name__)

# Check if these threaded queue is the best solution with while trues?

def response_generator(requestQueue, responseData, exit_signal):
    while not exit_signal.is_set():
        if not requestQueue.empty():
            request, token = requestQueue.get()
            print("Got request:", request)
            try:
                response = sw.processRequest(request[0], request[1])
            except Exception as ex:
                response = str(ex)
            if response == None:
                response = "Can't interpret request"
            responseData[token] = response
            print("response:", response)
        time.sleep(0.1)
    sw.teardownConnection(sh)

requestQueue = queue.Queue()
responseData = {}

exit_signal = threading.Event()
response_thread = threading.Thread(
    target=response_generator, args=(requestQueue, responseData, exit_signal)
)
response_thread.daemon = True
response_thread.start()

@app.errorhandler(Exception)
def handle_error(error):
    response = jsonify(f"Error: {error}")
    response.status_code = 500
    return response

@app.route("/api/tables/<table_name>", methods=["GET"])
def get_table_request(table_name):
    token = str(uuid.uuid4())
    data = ["getTableEntries", table_name]
    requestQueue.put((data, token))
    while True:
        if token in responseData:
            response = responseData.pop(token)
            print(response)
            return jsonify({"table_data": response}), 200
        time.sleep(0.1)

@app.route("/api/tables/<table_name>", methods=["DELETE"])
def delete_table_request(table_name):
    token = str(uuid.uuid4())
    data = ["clearTable", table_name]
    requestQueue.put((data, token))
    while True:
        if token in responseData:
            response = responseData.pop(token)
            return jsonify({"response": response}), 200
        time.sleep(0.1)

@app.route("/api/tables/", methods=["POST"])
def insert_into_table_request():
    requestData = request.json
    token = str(uuid.uuid4())
    data = ["insertTableEntry", requestData]
    requestQueue.put((data, token))
    while True:
        if token in responseData:
            response = responseData.pop(token)
            return jsonify({"response": response}), 200
        time.sleep(0.1)

if __name__ == "__main__":
    if len( sys.argv ) != 3:
      print(f"ArgumentError: use {sys.argv[0]} <p4info.txt> <prog.json>")
      sys.exit(-1)
    p4infoFile = sys.argv[1]
    binFile = sys.argv[2]
    #p4infoFile = "d6g-gw-v4.p4runtime.txt"
    #binFile = "../data-plane/d6g-gw-v4.json"
    sw.uploadDP(p4infoFile, binFile)
    app.run(host='0.0.0.0', port=5000, debug=True)
