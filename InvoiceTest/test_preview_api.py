import urllib.request
import urllib.parse
import urllib.error
import json

# Login first
login_data = json.dumps({'username': 'a', 'password': '1'}).encode()
req_login = urllib.request.Request(
    'http://127.0.0.1:8000/api/auth/login/',
    data=login_data,
    headers={'Content-Type': 'application/json'}
)
res = urllib.request.urlopen(req_login)
token = json.loads(res.read())['access']

boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
file_path = 'test_staging_scenarios.xlsx'

with open(file_path, 'rb') as f:
    file_content = f.read()

data = (
    b'--' + boundary.encode() + b'\r\n'
    b'Content-Disposition: form-data; name="file"; filename="test_staging_scenarios.xlsx"\r\n'
    b'Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet\r\n\r\n'
    + file_content + 
    b'\r\n--' + boundary.encode() + b'--\r\n'
)

req = urllib.request.Request(
    'http://127.0.0.1:8000/api/retail/bulk-preview/',
    data=data,
    headers={'Content-Type': f'multipart/form-data; boundary={boundary}', 'Authorization': f'Bearer {token}'}
)

try:
    res = urllib.request.urlopen(req)
    print("SUCCESS", res.getcode())
    print(res.read().decode())
except urllib.error.HTTPError as e:
    print("ERROR", e.code)
    print(e.read().decode())
