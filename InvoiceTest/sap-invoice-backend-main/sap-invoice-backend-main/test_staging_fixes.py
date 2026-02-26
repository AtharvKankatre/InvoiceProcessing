# coding: utf-8
"""
Comprehensive API test for all 10 staging grid fixes.
Uses only stdlib — no `requests` dependency.
"""
import os, sys, json, django
from urllib.request import Request, urlopen
from urllib.error import HTTPError

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sap_invoice.settings')
django.setup()

BASE = "http://localhost:8000"
PASS_COUNT = 0
FAIL_COUNT = 0

def test(name, condition, detail=""):
    global PASS_COUNT, FAIL_COUNT
    if condition:
        PASS_COUNT += 1
        print(f"  PASS: {name}")
    else:
        FAIL_COUNT += 1
        print(f"  FAIL: {name} -- {detail}")

def api_post_json(path, data, token):
    """POST JSON to the API."""
    body = json.dumps(data).encode()
    req = Request(f"{BASE}{path}", data=body, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }, method="POST")
    try:
        resp = urlopen(req, timeout=15)
        return resp.status, json.loads(resp.read().decode())
    except HTTPError as e:
        return e.code, json.loads(e.read().decode()) if e.read else {}

def api_post_file(path, filepath, token):
    """POST multipart file upload."""
    import mimetypes
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    filename = os.path.basename(filepath)
    mime = mimetypes.guess_type(filepath)[0] or "application/octet-stream"
    with open(filepath, "rb") as f:
        file_data = f.read()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode() + file_data + f"\r\n--{boundary}--\r\n".encode()
    req = Request(f"{BASE}{path}", data=body, headers={
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Authorization": f"Bearer {token}"
    }, method="POST")
    try:
        resp = urlopen(req, timeout=30)
        return resp.status, json.loads(resp.read().decode())
    except HTTPError as e:
        body = e.read()
        return e.code, json.loads(body.decode()) if body else {}

# ── Get auth token ──
print("=" * 60)
print("AUTHENTICATING...")
from django.contrib.auth import get_user_model
User = get_user_model()
user = User.objects.first()
if not user:
    print("No users in DB!")
    sys.exit(1)

from rest_framework_simplejwt.tokens import RefreshToken
token = str(RefreshToken.for_user(user).access_token)
print(f"Got token for: {user.username}")

# ═══════════════════════════════════════════════════════════
# TEST 1: Preview endpoint with test file
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("TEST 1: PREVIEW ENDPOINT")
print("=" * 60)

test_file = r"D:\Inpinite\InvoiceTest\STAGING_TEST_FILE.xlsx"
code, data = api_post_file("/api/retail/bulk-preview/", test_file, token)
test("Preview returns 200", code == 200, f"Got {code}")

if code == 200:
    rows = data.get("rows", [])
    inv = data.get("part_inventory", {})
    valid_rows = [r for r in rows if r["is_valid"]]
    invalid_rows = [r for r in rows if not r["is_valid"]]
    
    test(f"Has {len(rows)} rows total", len(rows) == 14, f"Got {len(rows)}")
    test(f"Has valid rows", len(valid_rows) >= 1, f"Got {len(valid_rows)}")
    test(f"Has invalid rows", len(invalid_rows) >= 1, f"Got {len(invalid_rows)}")
    
    # Row 4: missing date
    r4 = next((r for r in rows if r["row_id"] == 4), None)
    if r4:
        test("Row 4 (no date): invalid", not r4["is_valid"])
    
    # Row 6: fake part
    r6 = next((r for r in rows if r["row_id"] == 6), None)
    if r6:
        test("Row 6 (fake part): invalid", not r6["is_valid"])
        test("Row 6 has part_number error", "part_number" in r6.get("errors", {}))
    
    # Row 12: dup invoice
    r12 = next((r for r in rows if r["row_id"] == 12), None)
    if r12:
        test("Row 12 (dup invoice): invalid", not r12["is_valid"])
    
    # Row 14: stock exceeded
    r14 = next((r for r in rows if r["row_id"] == 14), None)
    if r14:
        test("Row 14 (999999 qty): invalid", not r14["is_valid"])
        test("Row 14 has qty error", "qty" in r14.get("errors", {}))

# ═══════════════════════════════════════════════════════════
# TEST 2: Commit endpoint guards (items 2, 3)
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("TEST 2: COMMIT GUARDS (items 2, 3)")
print("=" * 60)

# Empty rows
code, body = api_post_json("/api/retail/bulk-upload-commit/", {"rows": []}, token)
test("Empty rows -> 400", code == 400, f"Got {code}")

# 501 rows (item 2: row-count limit)
fake = [{"row_id": i, "data": {"part_number": "X"}} for i in range(501)]
code, body = api_post_json("/api/retail/bulk-upload-commit/", {"rows": fake}, token)
test("501 rows -> 400 (MAX_ROWS)", code == 400, f"Got {code}")
if code == 400:
    err = body.get("error", "")
    test("Error says 'Maximum'", "maximum" in err.lower() or "too many" in err.lower(), err)

# Bad shape (item 3)
code, body = api_post_json("/api/retail/bulk-upload-commit/", {"rows": [{"no_data": True}]}, token)
test("Bad payload shape -> 400", code == 400, f"Got {code}")

# Bad selected_invoices (item 3)
bad = [{"row_id": 1, "data": {"part_number": "X"}, "selected_invoices": [{"missing": "fields"}]}]
code, body = api_post_json("/api/retail/bulk-upload-commit/", {"rows": bad}, token)
test("Bad selected_invoices -> 400", code == 400, f"Got {code}")

# Non-numeric qty in selection (item 3)
bad2 = [{"row_id": 1, "data": {"part_number": "X"}, "selected_invoices": [{"invoice_id": 1, "qty": "abc"}]}]
code, body = api_post_json("/api/retail/bulk-upload-commit/", {"rows": bad2}, token)
test("Non-numeric sel qty -> 400", code == 400, f"Got {code}")

# ═══════════════════════════════════════════════════════════
# TEST 3: Frontend code checks (items 1, 4-9)
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("TEST 3: FRONTEND CODE CHECKS (items 1, 4-9)")
print("=" * 60)

fe = r"D:\Inpinite\InvoiceTest\cooper_frontend-main\cooper_frontend-main\src\components\BulkUploadStaging.tsx"
with open(fe, "r", encoding="utf-8") as f:
    code = f.read()

test("[1] useRef import", "useRef" in code)
test("[1] commitGuard ref", "commitGuard.current" in code)
test("[4] window.confirm", "window.confirm" in code)
test("[4] 'cannot be undone'", "cannot be undone" in code)
test("[5] usd_rate > 0 check", "usdVal <= 0" in code)
test("[5] conv_rate > 0 check", "convVal <= 0" in code)
test("[6] Number.isInteger", "Number.isInteger" in code)
test("[6] 'whole number' msg", "whole number" in code)
test("[7] partNumber fallback", "part_number || ''" in code)
test("[8] validCount display", "validCount" in code)
test("[8] invalidCount display", "invalidCount" in code)
test("[9] handleRemoveAllInvalid", "handleRemoveAllInvalid" in code)
test("[9] 'Remove All Invalid' text", "Remove All Invalid" in code)

# ═══════════════════════════════════════════════════════════
# TEST 4: DashboardPage fix (item 10)
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("TEST 4: DASHBOARD SUCCESS FLOW (item 10)")
print("=" * 60)

dp = r"D:\Inpinite\InvoiceTest\cooper_frontend-main\cooper_frontend-main\src\pages\DashboardPage.tsx"
with open(dp, "r", encoding="utf-8") as f:
    dp_code = f.read()

test("[10] Has success alert", "alert(" in dp_code and "Successfully" in dp_code)
test("[10] Page reloads after commit", "window.location.reload" in dp_code)
test("[10] No stale BulkUploadResult import", "BulkUploadResult" not in dp_code)
test("[10] No stale showBulkResultModal", "showBulkResultModal" not in dp_code)

# ═══════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 60)
total = PASS_COUNT + FAIL_COUNT
print(f"RESULTS: {PASS_COUNT}/{total} passed, {FAIL_COUNT} failed")
if FAIL_COUNT == 0:
    print("ALL TESTS PASSED!")
else:
    print(f"{FAIL_COUNT} test(s) need attention")
print("=" * 60)
