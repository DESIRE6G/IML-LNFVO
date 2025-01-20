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
    # sh = sw.setupConnection()
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

exit_signal = threading.Event()  # Define exit signal event
response_thread = threading.Thread(
    target=response_generator, args=(requestQueue, responseData, exit_signal)
)
response_thread.daemon = True
response_thread.start()

# Dictionary to store tokens and corresponding response data


@app.route("/api/tables/<table_name>", methods=["GET"])
def get_table_request(table_name):
    token = str(uuid.uuid4())
    data = ["getTable", table_name]
    requestQueue.put((data, token))
    # Wait for response with the same token
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


@app.route("/api/service/create", methods=["POST"])
def create_service_request():
    token = str(uuid.uuid4())
    requestData = request.json
    print("got request", requestData)
    data = ["createService", requestData]
    requestQueue.put((data, token))
    while True:
        if token in responseData:
            response = responseData.pop(token)
            return jsonify({"response": response}), 200
        time.sleep(1)


@app.route("/api/UE/setHH", methods=["POST"])
def set_HH_request():
    token = str(uuid.uuid4())
    requestData = request.json
    print("got request", requestData)
    data = ["setHH", requestData]
    requestQueue.put((data, token))
    while True:
        if token in responseData:
            response = responseData.pop(token)
            return jsonify({"response": response}), 200
        time.sleep(1)


@app.route("/api/UE/unsetHH", methods=["POST"])
def unset_HH_request():
    token = str(uuid.uuid4())
    requestData = request.json
    print("got request", requestData)
    data = ["unsetHH", requestData]
    requestQueue.put((data, token))
    while True:
        if token in responseData:
            response = responseData.pop(token)
            return jsonify({"response": response}), 200
        time.sleep(1)


@app.route("/api/UE/attach", methods=["POST"])
def attach_UE_request():
    token = str(uuid.uuid4())
    requestData = request.json
    print("got request", requestData)
    data = ["attachUE", requestData]
    requestQueue.put((data, token))
    while True:
        if token in responseData:
            response = responseData.pop(token)
            return jsonify({"response": response}), 200
        time.sleep(1)


@app.route("/api/UE/detach", methods=["POST"])
def detach_UE_request():
    token = str(uuid.uuid4())
    requestData = request.json
    print("got request", requestData)
    data = ["detachUE", requestData]
    requestQueue.put((data, token))
    while True:
        if token in responseData:
            response = responseData.pop(token)
            return jsonify({"response": response}), 200
        time.sleep(0.1)


@app.route("/api/UE/move", methods=["POST"])
def move_UE_request():
    token = str(uuid.uuid4())
    requestData = request.json
    print("got request", requestData)
    data = ["moveUE", requestData]
    requestQueue.put((data, token))
    while True:
        if token in responseData:
            response = responseData.pop(token)
            return jsonify({"response": response}), 200
        time.sleep(0.1)


if __name__ == "__main__":
    app.run(debug=True)
