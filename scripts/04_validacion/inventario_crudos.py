import zipfile, io, os, sys, csv, hashlib, re
ZIP="/home/spawnmc/Code/TesysTMP/OneDrive_2_7-11-2026.zip"
from pathlib import Path
BASE=str(Path(__file__).resolve().parents[2] / "data" / "mensuales")
OUT=sys.argv[1]
rows=[]
def periodo(s):
    m=re.search(r'(20\d{2})(0[1-9]|1[0-2])',s) 
    if m: return m.group(1)+m.group(2)
    m=re.search(r'(0[1-9]|1[0-2])(20\d{2})',s)
    return m.group(2)+m.group(1) if m else ""
def tipo(s):
    t=s.lower()
    if "impoq1" in t: return "importacion_Q1"
    if "impoq2" in t: return "importacion_Q2"
    if "expo" in t: return "exportacion"
    if "impo" in t: return "importacion"
    if "prov" in t: return "proveedores"
    return "otro"
# 1) zip de TesysTMP (nombres, tamaños, CRC; entra a zips anidados)
z=zipfile.ZipFile(ZIP)
for i in z.infolist():
    if i.is_dir(): continue
    n=i.filename
    if n.lower().endswith(".zip"):
        try:
            inner=zipfile.ZipFile(io.BytesIO(z.read(i)))
            for j in inner.infolist():
                if j.is_dir(): continue
                rows.append(("tesystmp_zip",n,j.filename,j.file_size,f"{j.CRC:08x}",periodo(n) or periodo(j.filename),tipo(n+"/"+j.filename)))
        except zipfile.BadZipFile:
            rows.append(("tesystmp_zip",n,"<ZIP_INVALIDO>",i.file_size,f"{i.CRC:08x}",periodo(n),tipo(n)))
    else:
        rows.append(("tesystmp_zip",n,"",i.file_size,f"{i.CRC:08x}",periodo(n),tipo(n)))
# 2) crudos locales
for root,_,files in os.walk(BASE):
    if "/raw/" not in root+"/": continue
    for f in files:
        p=os.path.join(root,f); rel=os.path.relpath(p,BASE)
        h=hashlib.sha256()
        with open(p,"rb") as fh:
            for b in iter(lambda:fh.read(1<<20),b""): h.update(b)
        rows.append(("local_raw",rel,"",os.path.getsize(p),h.hexdigest()[:16],periodo(rel),tipo(rel)))
with open(OUT,"w",newline="") as fh:
    w=csv.writer(fh); w.writerow(["fuente","archivo","interno","bytes","hash","periodo","tipo"]); w.writerows(rows)
print(len(rows),"filas")
