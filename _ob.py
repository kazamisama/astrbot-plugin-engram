src=open('hippocampus/service.py',encoding='utf-8').read().splitlines()
import re
start=None
for ln,l in enumerate(src,1):
    if re.search(r'def observe\(', l): start=ln
    if start and start<=ln<start+70: print(ln,l)