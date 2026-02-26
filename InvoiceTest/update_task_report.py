import openpyxl

path = 'd:\\Inpinite\\InvoiceTest\\Cooper_Task_Report.xlsx'
wb = openpyxl.load_workbook(path)
ws = wb.active

# 1. Mark Req 9 (Bulk Upload) items as Completed
completed_count = 0
for row in ws.iter_rows(min_row=2):
    if len(row) >= 4 and row[0].value:
        req_id = str(row[0].value).strip()
        if req_id.startswith('9.') and row[3].value != 'Completed':
            row[3].value = 'Completed'
            completed_count += 1

# 2. Add Req 11 New Requirements before the "Summary" block
insert_row_idx = None
for i, row in enumerate(ws.iter_rows(min_row=1), start=1):
    if len(row) > 0 and str(row[0].value).strip() == 'Summary':
        insert_row_idx = i
        break

if insert_row_idx:
    ws.insert_rows(insert_row_idx, amount=7)
    
    # Add Req 11 header
    base_row = insert_row_idx
    ws.cell(row=base_row, column=1, value='Req 11')
    ws.cell(row=base_row, column=2, value='Interactive Bulk-Upload Staging Area')
    ws.cell(row=base_row, column=3, value='Browser-based Excel preview with live database stock comparison and inline error editing')
    
    # Subtasks
    tasks = [
        ('11.1', 'Dry Run API Endpoint', 'Parse Excel, compare with DB stock, and return validation JSON without saving', 'Pending'),
        ('11.2', 'Interactive Staging Grid', 'Editable UI table to show valid/invalid rows side-by-side with required stock', 'Pending'),
        ('11.3', 'Inline Error Correction', 'Allow users to fix typos directly in the browser and re-validate instantly', 'Pending'),
        ('11.4', 'Manual Invoice Override', 'Allow users to select specific wholesale invoices per row instead of automatic FIFO', 'Pending'),
        ('11.5', 'Atomic Batch Commit API', 'Save the entire batch securely to the database with transaction rollback for integrity', 'Pending'),
    ]
    
    for i, t in enumerate(tasks, start=1):
        ws.cell(row=base_row+i, column=1, value=t[0])
        ws.cell(row=base_row+i, column=2, value=t[1])
        ws.cell(row=base_row+i, column=3, value=t[2])
        ws.cell(row=base_row+i, column=4, value=t[3])

# 3. Update the summary numbers mathematically
for row in ws.iter_rows(min_row=1):
    val = str(row[0].value).strip() if row[0].value else ""
    if val == 'Total New Requirements':
        row[1].value = 11
    elif val == 'Total Sub-tasks':
        row[1].value = 44
    elif val == 'Completed Sub-tasks':
        row[1].value = 38
    elif val == 'Pending Sub-tasks':
        row[1].value = 6
        
# 4. Update the "Pending Items" list at the bottom to reflect reality
# Clear out older pending items
pending_idx = None
for i, row in enumerate(ws.iter_rows(min_row=1), start=1):
    if str(row[0].value).strip() == 'Pending Items':
        pending_idx = i
        break

if pending_idx:
    # Clear the next 5 rows
    for i in range(1, 6):
        ws.cell(row=pending_idx+i, column=1, value='')
        ws.cell(row=pending_idx+i, column=2, value='')
        ws.cell(row=pending_idx+i, column=4, value='')

    new_pending = [
        ('1', 'Production deployment using Docker (Req 10.4)', 'Pending'),
        ('2', 'Interactive Bulk-Upload Staging Area (Req 11)', 'Pending'),
        ('3', 'Bug fixes reported during UAT / production testing', 'Pending'),
        ('4', 'Minor UI enhancements based on client feedback', 'Pending'),
    ]
    for i, item in enumerate(new_pending, start=1):
        ws.cell(row=pending_idx+i, column=1, value=item[0])
        ws.cell(row=pending_idx+i, column=2, value=item[1])
        ws.cell(row=pending_idx+i, column=4, value=item[2])

wb.save(path)
print("Updated Excel file successfully.")
