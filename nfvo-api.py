import sys
import traceback
import time
import os
from flask import Flask, request, jsonify
from kubernetes import client, config, watch
from ruamel.yaml import YAML
from subprocess import run

from lnfvo import lnfvo

app = Flask(__name__)

DEFAULT_NAMESPACE = 'desire6g'
DEFAULT_CHART = './graph-chart'
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

@app.route("/iml/yaml/deploy/<id>", methods=["DELETE"])
def deleteDeployment(id):
  result = run(['helm', 'uninstall', '--namespace', DEFAULT_NAMESPACE, f'deploy-{id}'], capture_output = True, text = True)

  if result.stderr:
    return jsonify({"response": result.stderr}), 500
  else:
    return jsonify({"response": f"Succesfull deletion of the deployment with id: {id}"}), 200

@app.route("/iml/yaml/deploy", methods=["POST"])
def deploy_yaml():
  #deploy_start = time.time()
  path = os.path.join(app.config['UPLOAD_FOLDER'], "uploaded.yml")
  file = request.files['file']
  file.save(path)

  with open(path, 'r') as f:
    try:
      yaml=YAML(typ='safe')
      yaml_data = yaml.load(f)

      deploy_id = get_next_deploy_id()
      values_path = os.path.join(DEPLOY_FOLDER, f'values-{deploy_id}.yaml')
      data = lnfvo.generate_values(yaml_data, values_path)

      result = run(['helm', 'install', '--namespace', DEFAULT_NAMESPACE, '--create-namespace', '--post-renderer', f'{DEFAULT_CHART}/post-render.sh', '-f', values_path, f'deploy-{deploy_id}', DEFAULT_CHART], capture_output = True, text = True)
        #helm_start = time.time()
        #helm_end = time.time()

      if result.stderr:
        response = (f"Failed to deploy: {result.stderr}", 500)
        return jsonify({"response": response[0]}), response[1]
      else:
        response = (f"Deployed: {yaml_data['lnsd']['ns']['name']} as id {deploy_id}", 200)

      need_cp = lnfvo.getNFCPstofill(data)

      w = watch.Watch()
      for event in w.stream(func=core_v1.list_namespaced_pod,
                            namespace='desire6g',
                            timeout_seconds=60):
        if event["object"].status.phase == "Running":
        #cont_start = time.time()
            for s in need_cp[:]:
              if event['object'].metadata.name.startswith(s):
                #cont_end = time.time()
                #print(f"time to gw cont ready: {cont_end - cont_start}")
                mgmt_ip = event['object'].status.pod_ip
                #cp_start = time.time()
                lnfvo.fillCPofNF(data, s, mgmt_ip)
                #cp_end = time.time()
                #print(f"time to fill cp: {cp_end - cp_start}")
                need_cp.remove(s)
            if not need_cp:
              w.stop()

    except Exception as ex:
      response = (f'{type(ex).__name__}: {ex.args}', 500)
      traceback.print_exc()

  #deploy_end = time.time()
  #print(f"time to deploy as a whole: {deploy_end - deploy_start}")
  return jsonify({"response": response[0]}), response[1]

if __name__ == "__main__":
  path = "./site-config.yml"
  if len( sys.argv ) > 1:
    path = sys.argv[1]
  predeployed = lnfvo.parse_siteconfig(path)
  app.run(host='0.0.0.0', debug=True)
