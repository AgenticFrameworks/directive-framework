#!/usr/bin/env python3
import hashlib, pathlib, tarfile
root=pathlib.Path(__file__).resolve().parents[1]; out=root/'dist'; out.mkdir(exist_ok=True)
allow=['AUTO-HANDOFF-SPEC.md','EXECUTOR-SPEC.md','RUNTIME-SPEC.md','README.md','LICENSE','gates','tools','planning-directives','validation-directives','review-directives','execution-directives','.claude-plugin','portable']
files=[]
for x in allow:
 p=root/x
 if p.is_file(): files.append(p)
 elif p.is_dir(): files += [q for q in p.rglob('*') if q.is_file() and '__pycache__' not in q.parts]
t=out/'directive-framework-v1.1.tar.gz'
with tarfile.open(t,'w:gz',format=tarfile.PAX_FORMAT) as z:
 for p in sorted(files): z.add(p,arcname=str(pathlib.Path('directive-framework')/p.relative_to(root)),recursive=False)
print(t,hashlib.sha256(t.read_bytes()).hexdigest())
