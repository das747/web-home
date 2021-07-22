# Running on Raspberry Pi 1
import socketio

sio = socketio.Client()

status = False


@sio.event
def connect():
    print('connection established')


@sio.event
def get_msg(data):
    status = data['status']
    print('Received data from server: {}'.format(data))


@sio.event
def disconnect():
    print('disconnected from server')


while 1:
    try:
        sio.connect('http://localhost:5000', headers={'device_id': '12345678'})
    except Exception:
        print('failed to connect to server...')
    else:
        break
