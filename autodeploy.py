from flask import Blueprint, request
import hmac
import os

SUPER_SECRET_KEY = bytes(open('deploy_secret_key.txt', mode='r').read(), 'utf8')
blueprint = Blueprint('autodeployment', __name__, template_folder='templates')


@blueprint.route('/deploy', methods=['POST'])
def autodeploy():
    hex_digest = request.headers['X-Hub-Signature']
    payload = request.json
    hasher = hmac.new(SUPER_SECRET_KEY, request.data, 'sha1')
    if (hmac.compare_digest(hex_digest, hasher.hexdigest())
            and payload['refs'].split('/', 2)[2] == 'deploy'):
        os.system('git pull && sudo systemctl restart webhome')

