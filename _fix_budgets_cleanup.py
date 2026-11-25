from pathlib import Path
p = Path(r'D:\WorkSpace\ERPAethereon\frontend\src\app\pages\budgets\budgets.component.ts')
lines = p.read_text(encoding='utf-8', errors='replace').splitlines(keepends=True)
# Remove lines 165-169 (0-based 164-168): the duplicate openCdpModal block
# Original: 160-164 are first openCdpModal + close? let us look: line 160 is "  openCdpModal..." (1-based), 161,162,163,164 is "  }", 165 is duplicate start
# Better: rebuild
new_lines = []
skip = False
for i,l in enumerate(lines):
    # skip duplicate block: lines 165-169 in 1-based => i from 164 to 168
    if i == 164:  # 1-based 165
        # check if this is the duplicate openCdpModal
        if 'openCdpModal' in l:
            # skip this and next 4 lines (165,166,167,168,169 => 5 lines total: i, i+1, i+2, i+3, i+4)
            skip_count = 5
            # handle by setting a counter
            pass
    new_lines.append(l)
# easier approach: filter out the specific duplicate lines
result = []
i = 0
while i < len(lines):
    if i == 164 and 'openCdpModal' in lines[i]:
        # skip 5 lines: 164,165,166,167,168
        i += 5
        continue
    result.append(lines[i])
    i += 1
p.write_text(''.join(result), encoding='utf-8')
print('done')
