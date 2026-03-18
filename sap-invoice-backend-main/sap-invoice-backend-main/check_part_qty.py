import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'InvoiceProcessing.settings')
django.setup()

from sales.services.stock_ledger import StockLedgerService

def check_discrepancies():
    print("Generating Stock Ledger (Sheet 1)...")
    ledger_data = StockLedgerService.get_ledger_data('01-04-2025', '11-03-2026')
    
    s1_totals = {}
    for row in ledger_data:
        party = row.get("Party Name", "Unknown")
        s1_totals[party] = {
            'qty': int(row.get("Closing Stock Qty", 0) or 0),
            'fc': round(float(row.get("Closing Stock FC Value", 0) or 0), 2),
            'inr': round(float(row.get("Closing Stock INR Value", 0) or 0), 2)
        }
        
    print("Generating Part-Wise Tracking (Sheet 3)...")
    partwise_data = StockLedgerService.get_partwise_consumption_data('01-04-2025', '11-03-2026')
    
    s3_totals = {}
    for row in partwise_data:
        if row.get('_row_type') == 'customer_subtotal':
            party_raw = row.get("Party Name", "")
            party = party_raw.replace(" — Despatch Total", "")
            
            if party not in s3_totals:
                s3_totals[party] = {'qty': 0, 'fc': 0.0, 'inr': 0.0}
            
            s3_totals[party]['qty'] += int(row.get("Closing Qty", 0) or 0)
            s3_totals[party]['fc'] += round(float(row.get("Closing FC", 0) or 0), 2)
            s3_totals[party]['inr'] += round(float(row.get("Closing INR", 0) or 0), 2)

    print("\n=== COMPARING SH1 vs SH3 ===")
    all_parties = set(list(s1_totals.keys()) + list(s3_totals.keys()))
    
    mismatch_found = False
    for p in sorted(all_parties):
        # Ignore empty party
        if not p.strip() or p == 'Unknown':
            continue
            
        s1 = s1_totals.get(p, {'qty': 0, 'fc': 0, 'inr': 0})
        s3 = s3_totals.get(p, {'qty': 0, 'fc': 0, 'inr': 0})
        
        if s1['qty'] != s3['qty'] or abs(s1['fc'] - s3['fc']) > 1 or abs(s1['inr'] - s3['inr']) > 1:
            print(f"MISMATCH FOR: {p}")
            print(f"  SH1 (Stock Ledger): QTY={s1['qty']}, FC={s1['fc']}, INR={s1['inr']}")
            print(f"  SH3 (Part-Wise):    QTY={s3['qty']}, FC={s3['fc']}, INR={s3['inr']}")
            mismatch_found = True
            
    if not mismatch_found:
        print("PERFECT MATCH FOR ALL CUSTOMERS!")

check_discrepancies()
