"""
fix_retail_invoice_numbers.py
==============================
One-time script to update InvoiceEntry records that have a NULL/empty
retail_invoice_number, using data from a CSV or Excel file.

HOW TO USE:
-----------
1. Prepare your data file (CSV or Excel) with these columns:
       date               | part_number      | retail_invoice_number
       2025-01-11         | PART-A400        | RTL-INV-001
       2025-01-16         | PART-A400        | RTL-INV-002

   - date format: YYYY-MM-DD
   - part_number: the RETAIL part number (as stored in InvoiceEntry.part_number)
                  OR the SAP part number (script will try both via the mapping table)
   - retail_invoice_number: the correct invoice number to fill in

2. Set the FILE_PATH variable below to point to your file.

3. Run from the Django project root:
       python fix_retail_invoice_numbers.py

   OR as a Django shell script:
       python manage.py shell < fix_retail_invoice_numbers.py

MATCHING LOGIC:
---------------
- Matches by: date + part_number (exact)
- Only updates records where retail_invoice_number IS NULL or empty
- If multiple records match the same date+part, updates ALL of them
  (you can change MATCH_MODE to 'first' to only update the first match)
- Prints a full report of what was updated and what was skipped

SAFE TO RUN MULTIPLE TIMES:
----------------------------
- Already-filled records are never overwritten (only NULL/empty ones are touched)
- Run in DRY_RUN=True mode first to preview changes without saving
"""

import os
import sys
import django

# ─── CONFIGURATION ────────────────────────────────────────────────────────────

# Path to your CSV or Excel file
FILE_PATH = "retail_invoice_data.csv"   # ← Change this to your file path

# Set to True to preview changes without saving to the database
DRY_RUN = True   # ← Change to False when you're ready to apply

# Match mode: 'all' = update all matching records, 'first' = only the first
MATCH_MODE = "all"

# Column names in your file (change if your file uses different headers)
COL_DATE = "date"
COL_PART = "part_number"
COL_INVOICE = "retail_invoice_number"

# ─── DJANGO SETUP ─────────────────────────────────────────────────────────────

# Only needed when running as a standalone script (not via manage.py shell)
if "DJANGO_SETTINGS_MODULE" not in os.environ:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sap_invoice.settings")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    django.setup()

# ─── IMPORTS (after django.setup) ─────────────────────────────────────────────

import pandas as pd
from datetime import datetime
from retail.models import InvoiceEntry
from sales.models import InvoiceRetailPartMap

# ─── LOAD FILE ────────────────────────────────────────────────────────────────

print(f"\n{'='*60}")
print(f"  Retail Invoice Number Fix Script")
print(f"  File: {FILE_PATH}")
print(f"  Dry Run: {DRY_RUN}")
print(f"{'='*60}\n")

if not os.path.exists(FILE_PATH):
    print(f"ERROR: File not found: {FILE_PATH}")
    print("Please set FILE_PATH to the correct path of your CSV or Excel file.")
    sys.exit(1)

if FILE_PATH.endswith(".csv"):
    df = pd.read_csv(FILE_PATH)
elif FILE_PATH.endswith((".xlsx", ".xls")):
    df = pd.read_excel(FILE_PATH)
else:
    print("ERROR: Unsupported file format. Use .csv, .xlsx, or .xls")
    sys.exit(1)

# Validate required columns
required_cols = {COL_DATE, COL_PART, COL_INVOICE}
missing = required_cols - set(df.columns)
if missing:
    print(f"ERROR: Missing columns in file: {missing}")
    print(f"Found columns: {list(df.columns)}")
    sys.exit(1)

print(f"Loaded {len(df)} rows from file.\n")

# ─── BUILD RETAIL PART LOOKUP (SAP → retail) ──────────────────────────────────

# If the file uses SAP part numbers, we need to map them to retail part numbers
all_mappings = InvoiceRetailPartMap.objects.all()
sale_to_retail = {}
for m in all_mappings:
    sale_to_retail.setdefault(m.sale_part_number, []).append(m.retail_part_number)

# ─── PROCESS EACH ROW ─────────────────────────────────────────────────────────

updated_count = 0
skipped_count = 0
not_found_count = 0

for idx, row in df.iterrows():
    raw_date = str(row[COL_DATE]).strip()
    raw_part = str(row[COL_PART]).strip()
    new_invoice_num = str(row[COL_INVOICE]).strip()

    if not new_invoice_num or new_invoice_num.lower() in ("nan", "none", ""):
        print(f"  Row {idx+2}: SKIP — retail_invoice_number is empty in file")
        skipped_count += 1
        continue

    # Parse date
    try:
        parsed_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
    except ValueError:
        try:
            parsed_date = datetime.strptime(raw_date, "%d-%m-%Y").date()
        except ValueError:
            print(f"  Row {idx+2}: SKIP — cannot parse date '{raw_date}'")
            skipped_count += 1
            continue

    # Determine which part numbers to search for
    # Try the given part number directly, plus any retail mappings if it's a SAP part
    search_parts = {raw_part}
    if raw_part in sale_to_retail:
        search_parts.update(sale_to_retail[raw_part])

    # Find matching InvoiceEntry records with NULL/empty retail_invoice_number
    qs = InvoiceEntry.objects.filter(
        date=parsed_date,
        part_number__in=search_parts,
    ).filter(
        # Only update records that are missing the invoice number
        retail_invoice_number__isnull=True
    ) | InvoiceEntry.objects.filter(
        date=parsed_date,
        part_number__in=search_parts,
        retail_invoice_number=""
    )

    # Deduplicate (union can produce duplicates)
    qs = InvoiceEntry.objects.filter(
        id__in=qs.values_list("id", flat=True)
    )

    if not qs.exists():
        print(f"  Row {idx+2}: NOT FOUND — date={parsed_date}, part={raw_part} "
              f"(no NULL records matching this date+part)")
        not_found_count += 1
        continue

    if MATCH_MODE == "first":
        qs = qs[:1]

    for entry in qs:
        print(f"  Row {idx+2}: {'[DRY RUN] Would update' if DRY_RUN else 'Updating'} "
              f"InvoiceEntry id={entry.id} | date={entry.date} | part={entry.part_number} "
              f"| retail_invoice_number: NULL → '{new_invoice_num}'")
        if not DRY_RUN:
            entry.retail_invoice_number = new_invoice_num
            entry.save(update_fields=["retail_invoice_number"])
        updated_count += 1

# ─── SUMMARY ──────────────────────────────────────────────────────────────────

print(f"\n{'='*60}")
print(f"  SUMMARY {'(DRY RUN — no changes saved)' if DRY_RUN else '(CHANGES APPLIED)'}")
print(f"{'='*60}")
print(f"  Records updated : {updated_count}")
print(f"  Rows skipped    : {skipped_count}  (empty invoice number in file)")
print(f"  Not found       : {not_found_count}  (no matching NULL record in DB)")
print(f"{'='*60}\n")

if DRY_RUN:
    print("  ⚠  DRY RUN mode — set DRY_RUN = False to apply changes.\n")
else:
    print("  ✅ Done! All matching records have been updated.\n")
