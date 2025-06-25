import threading
import queue
import time
import uuid
import signal
import sys
import shell_wrapper as sw
from flask import Flask, request, jsonify

app = Flask(__name__)

def response_generator(requestQueue, responseData, exit_signal):
    while not exit_signal.is_set():
        if not requestQueue.empty():
            request, token = requestQueue.get()
            print("Got request:", request)
            response = sw.processRequest(request[0], request[1])
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

@app.route("/api/tables/<table_name>", methods=["GET"])
def get_table_request(table_name):
    token = str(uuid.uuid4())
    data = ["getTable", table_name]
    requestQueue.put((data, token))
    while True:
        if token in responseData:
            response = responseData.pop(token)
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
    data = ["insertIntoTable", requestData]
    requestQueue.put((data, token))
    while True:
        if token in responseData:
            response = responseData.pop(token)
            return jsonify({"response": response}), 200
        time.sleep(0.1)

@app.route("/api/NFPortClassifier", methods=["POST"])
def create_NFPortClassifier_request():
    token = str(uuid.uuid4())
    requestData = request.json
    print("got request", requestData)
    data = ["NFPortClassifier", requestData]
    requestQueue.put((data, token))
    while True:
        if token in responseData:
            response = responseData.pop(token)
            return jsonify({"response": response}), 200
        time.sleep(0.1)

@app.route("/api/FWDGExecute", methods=["POST"])
def create_FWDGraphExecute_request():
    token = str(uuid.uuid4())
    requestData = request.json
    print("got request", requestData)
    data = ["FWDGExecute", requestData]
    requestQueue.put((data, token))
    while True:
        if token in responseData:
            response = responseData.pop(token)
            return jsonify({"response": response}), 200
        time.sleep(0.1)

@app.route("/api/NFForward", methods=["POST"])
def create_NFForward_request():
    token = str(uuid.uuid4())
    requestData = request.json
    print("got request", requestData)
    data = ["NFForward", requestData]
    requestQueue.put((data, token))
    while True:
        if token in responseData:
            response = responseData.pop(token)
            return jsonify({"response": response}), 200
        time.sleep(0.1)

@app.route("/api/NFForwardMAC", methods=["POST"])
def create_NFForwardMAC_request():
    token = str(uuid.uuid4())
    requestData = request.json
    print("got request", requestData)
    data = ["NFForwardMAC", requestData]
    requestQueue.put((data, token))
    while True:
        if token in responseData:
            response = responseData.pop(token)
            return jsonify({"response": response}), 200
        time.sleep(0.1)

@app.route("/api/NFForwardExternal", methods=["POST"])
def create_NFForwardExternal_request():
    token = str(uuid.uuid4())
    requestData = request.json
    print("got request", requestData)
    data = ["NFForwardExternal", requestData]
    requestQueue.put((data, token))
    while True:
        if token in responseData:
            response = responseData.pop(token)
            return jsonify({"response": response}), 200
        time.sleep(0.1)

if __name__ == "__main__":
    sw.uploadDP()
    app.run(host='0.0.0.0', port=5000, debug=True)
