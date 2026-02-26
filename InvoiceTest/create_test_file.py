import pandas as pd

# Creating test scenarios for the Bulk Upload Staging Grid
data = [
    {
        "part_number": "ART-X100", 
        "date": "2026-02-23", 
        "qty": 5, 
        "usd_rate": 10.50, 
        "conversion_rate": 83.20, 
        "retail_invoice_number": "TEST-INV-001"
    }, # Valid Row
    {
        "part_number": "ART-X100", 
        "date": "2026-02-23", 
        "qty": 999999, # Invalid: Not enough stock
        "usd_rate": 10.50, 
        "conversion_rate": 83.20, 
        "retail_invoice_number": "TEST-INV-002"
    },
    {
        "part_number": "FAKE-PART-999", # Invalid: Part doesn't exist
        "date": "2026-02-23", 
        "qty": 10, 
        "usd_rate": 15.00, 
        "conversion_rate": 83.20, 
        "retail_invoice_number": "TEST-INV-003"
    },
    {
        "part_number": "ART-X100", 
        "date": "", # Invalid: Missing date
        "qty": 5, 
        "usd_rate": "abc", # Invalid: Not a number
        "conversion_rate": 83.20, 
        "retail_invoice_number": "TEST-INV-004"
    },
    {
        "part_number": "ART-X100", 
        "date": "2026-02-23", 
        "qty": 2, 
        "usd_rate": 10.50, 
        "conversion_rate": 83.20, 
        "retail_invoice_number": "TEST-INV-001" # Invalid: Duplicate Invoice Number in file
    }
]

df = pd.DataFrame(data)

# Rename to match exact headers expected by the backend
df.columns = [
    "Retail Part Number (e.g. RETAIL-X100)",
    "Date (YYYY-MM-DD)",
    "Quantity to dispatch",
    "Selling USD rate per unit",
    "INR/USD Conversion (FX) rate",
    "Retail Invoice Number (must be unique)"
]

# Write to Excel
df.to_excel("test_staging_scenarios.xlsx", index=False)
print("Created test_staging_scenarios.xlsx")
