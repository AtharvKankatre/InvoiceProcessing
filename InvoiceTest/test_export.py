import urllib.request
import os

url = "http://127.0.0.1:8000/api/parts/all/export/"
print(f"Testing URL: {url}")

try:
    with urllib.request.urlopen(url) as response:
        print(f"Status Code: {response.getcode()}")
        if response.getcode() == 200:
            print("Success! Content-Type:", response.info().get_content_type())
            content = response.read()
            print(f"Downloaded {len(content)} bytes")
            with open("test_export_all.xlsx", "wb") as f:
                f.write(content)
            print("Saved test_export_all.xlsx")
        else:
            print("Failed:", response.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code} {e.reason}")
    print(e.read().decode('utf-8'))
except Exception as e:
    print(f"Error: {e}")
