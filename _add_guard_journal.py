from pathlib import Path
p = Path(r'D:\WorkSpace\ERPAethereon\backend\services\finance\app\main.py')
s = p.read_text(encoding='utf-8', errors='replace')
# find and replace
old = '    require_company(claims, fy["company_id"])\n    if fy["is_closed"]:\n        raise HTTPException(status_code=409, detail="El ejercicio fiscal est'
# find the actual string
idx = s.find(old)
if idx < 0:
    print('NO')
else:
    # replace up to the end of that line's detail
    # find the end of the raise line
    end = s.find('\n', idx + len(old))
    # but easier: replace the whole block
    old_block = '    require_company(claims, fy["company_id"])\n    if fy["is_closed"]:\n        raise HTTPException(status_code=409, detail="El ejercicio fiscal está cerrado.")'
    # try both encodings
    if old_block in s:
        new_block = '''    require_company(claims, fy["company_id"])
    acct_count = db.execute(text("SELECT COUNT(*) FROM accounts WHERE company_id = :cid AND is_active"), {"cid": fy["company_id"]}).scalar_one()
    if acct_count == 0:
        raise HTTPException(status_code=409, detail="No se puede crear asientos: debe crear/importar el Plan de Cuentas primero.")
    if fy["is_closed"]:
        raise HTTPException(status_code=409, detail="El ejercicio fiscal está cerrado.")'''
        s2 = s.replace(old_block, new_block, 1)
        p.write_text(s2, encoding='utf-8')
        print('OK')
    else:
        print('NO2')
