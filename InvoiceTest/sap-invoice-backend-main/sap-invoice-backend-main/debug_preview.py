# coding: utf-8
import os, json, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sap_invoice.settings')
django.setup()

from urllib.request import Request, urlopen
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken

user = get_user_model().objects.first()
token = str(RefreshToken.for_user(user).access_token)

tf = r"D:\Inpinite\InvoiceTest\STAGING_TEST_FILE.xlsx"
bd = "----B"
fn = os.path.basename(tf)
fd = open(tf, "rb").read()
body_str = "--" + bd + "\r\nContent-Disposition: form-data; name=\"file\"; filename=\"" + fn + "\"\r\nContent-Type: application/octet-stream\r\n\r\n"
body = body_str.encode() + fd + ("\r\n--" + bd + "--\r\n").encode()

req = Request(
    "http://localhost:8000/api/retail/bulk-preview/",
    data=body,
    headers={
        "Content-Type": "multipart/form-data; boundary=" + bd,
        "Authorization": "Bearer " + token
    },
    method="POST"
)
resp = urlopen(req, timeout=30)
data = json.loads(resp.read().decode())

for r in data["rows"]:
    s = "OK " if r["is_valid"] else "ERR"
    errs = r.get("errors", {})
    print("Row %2d: %s  errors=%s" % (r["row_id"], s, json.dumps(errs)))
