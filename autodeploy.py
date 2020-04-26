from flask import Blueprint, request
import hmac
import subprocess

SUPER_SECRET_KEY = open('deploy_secret_key.txt', mode='r').read().strip()
blueprint = Blueprint('autodeployment', __name__, template_folder='templates')


@blueprint.route('/deploy', methods=['POST'])
def autodeploy():
    res = SUPER_SECRET_KEY
    header_hex_digest = request.headers.get('X-Hub-Signature')
    if header_hex_digest is None:
        return 'No hash header'
    sha_name, signature = header_hex_digest.split('=')

    if sha_name != 'sha1':
        return 'Wrong sha type'
    res += '\n' + signature
    if request.data:
        hasher = hmac.new(SUPER_SECRET_KEY.encode('utf-8'), msg=request.data, digestmod='sha1')
        res += '\n' + hasher.hexdigest()
        if (not hmac.compare_digest(hasher.hexdigest(), signature)
                or request.json['ref'].split('/', 2)[2] != 'deploy'):
            return res + '\nSomething went wrong'
        subprocess.call(['/usr/bin/git', 'pull'])
        subprocess.call(['/usr/bin/sudo', 'systemctl', 'restart', 'webhome'])
        return res
