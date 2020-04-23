from requests import get, put, post
while 1:
    print(get('http://192.168.1.201:5000/api/v2/light').json())
