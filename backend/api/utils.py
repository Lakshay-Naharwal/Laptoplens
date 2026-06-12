import re

def get_cores(val):
    val = str(val).lower()
    if 'dual' in val: return 2
    if 'quad' in val: return 4
    if 'hexa' in val: return 6
    if 'octa' in val: return 8
    match = re.search(r'(\d+)\s*cores', val)
    return int(match.group(1)) if match else 4

def get_threads(val):
    match = re.search(r'(\d+)\s*threads', val)
    return int(match.group(1)) if match else 8

def get_cpu_brand(val):
    val = str(val).lower()
    if 'intel' in val: return 'Intel'
    if 'amd' in val or 'ryzen' in val or 'athlon' in val: return 'AMD'
    if 'apple' in val or 'm1' in val or 'm2' in val or 'm3' in val: return 'Apple'
    if 'snapdragon' in val: return 'Qualcomm'
    return 'Other'

def get_cpu_tier(val):
    val = str(val).lower()
    for tier in ['i9', 'i7', 'i5', 'i3', 'ultra 9', 'ultra 7', 'ultra 5']:
        if tier in val: return f"Core {tier}"
    for tier in ['ryzen 9', 'ryzen 7', 'ryzen 5', 'ryzen 3']:
        if tier in val: return tier.title()
    for tier in ['m1', 'm2', 'm3']:
        if tier in val: return tier.upper()
    for tier in ['celeron', 'pentium', 'athlon', 'snapdragon']:
        if tier in val: return tier.title()
    return 'Other'

def get_cpu_gen(val):
    val = str(val).lower()
    # Explicit "Xth Gen"
    match = re.search(r'(\d+)(st|nd|rd|th)\s*gen', val)
    if match:
        return f"{match.group(1)}th Gen"
    # Intel: "i5 12500H" -> 12th Gen
    if 'intel' in val:
        m = re.search(r'i[3579][-\s]*(\d{2})\d{2,3}', val)
        if m:
            return f"{m.group(1)}th Gen"
        if 'ultra' in val:
            return 'Core Ultra'
    # AMD: "Ryzen 5 5600H" -> 5000 Series
    if 'amd' in val or 'ryzen' in val:
        m = re.search(r'ryzen\s*\d[-\s]*(\d)\d{3}', val)
        if m:
            return f"{m.group(1)}000 Series"
    # Apple M1/M2/M3
    if 'apple' in val or 'm1' in val or 'm2' in val or 'm3' in val:
        m = re.search(r'(m[123])', val)
        if m:
            return f"{m.group(1).upper()} Series"
    return 'Other/Unknown'

def get_gpu_brand(val):
    val = str(val).lower()
    if any(k in val for k in ['nvidia', 'geforce', 'rtx', 'gtx']): return 'NVIDIA'
    if any(k in val for k in ['amd', 'radeon']): return 'AMD'
    if any(k in val for k in ['intel', 'iris', 'uhd']): return 'Intel'
    if any(k in val for k in ['apple', 'm1', 'm2', 'm3']): return 'Apple'
    return 'Other'

def get_gpu_vram(val):
    match = re.search(r'(\d+)gb', str(val).lower())
    return float(match.group(1)) if match else 0.0
