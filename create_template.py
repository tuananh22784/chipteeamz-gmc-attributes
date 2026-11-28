import sys,csv
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font,PatternFill,Alignment,Protection
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.utils import get_column_letter
sys.path.insert(0,str(Path(__file__).parent))
from material_sheet_sync import PENDING_FIELDS,RULE_FIELDS,HISTORY_FIELDS,build_pending

def create(audit,dest):
 pending=build_pending(audit)
 book=Workbook(); book.remove(book.active)
 for title,fields,data in [('Pending_Material',PENDING_FIELDS,pending),('Approved_Rules',RULE_FIELDS,[]),('History',HISTORY_FIELDS,[])]:
  ws=book.create_sheet(title); ws.append(fields)
  for row in data:ws.append([row.get(f,'') for f in fields])
  ws.freeze_panes='D2';ws.auto_filter.ref=ws.dimensions
  for cell in ws[1]:cell.fill=PatternFill('solid',fgColor='17365D');cell.font=Font(color='FFFFFF',bold=True);cell.alignment=Alignment(wrap_text=True)
  for col,key in enumerate(fields,1):
   ws.column_dimensions[get_column_letter(col)].width=min(62,max(15, len(key)+5))
  if title=='Pending_Material':
   for row in ws.iter_rows(min_row=2):
    for c in row:
     if fields[c.column-1] in ('scope','confirmed_style','confirmed_material','staff_note','status'):
      c.fill=PatternFill('solid',fgColor='FFF2CC')
   dv=DataValidation(type='list',formula1='"ITEM,STYLE"');ws.add_data_validation(dv);dv.add(f'I2:I100000')
   st=DataValidation(type='list',formula1='"PENDING,APPROVE"');ws.add_data_validation(st);st.add(f'M2:M100000')
  ws.sheet_view.showGridLines=False
 book.save(dest)
 return len(pending)

if __name__=='__main__':
 print(create(Path('/mnt/data/audit(10).csv'),Path('/mnt/data/material_employee_review_template.xlsx')))
