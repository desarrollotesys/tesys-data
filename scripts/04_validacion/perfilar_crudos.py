import zipfile, io, csv, re, sys, collections
ZIP="/home/spawnmc/Code/TesysTMP/OneDrive_2_7-11-2026.zip"
OUT=sys.argv[1]
re_d2=re.compile(rb'\d{2}/\d{2}/\d{2}(?!\d)'); re_d4=re.compile(rb'\d{2}/\d{2}/\d{4}'); re_iso=re.compile(rb'\d{4}-\d{2}-\d{2}')
def per(s):
    m=re.search(r'(20\d{2})(0[1-9]|1[0-2])',s); 
    if m: return m.group(1)+m.group(2)
    m=re.search(r'(0[1-9]|1[0-2])(20\d{2})',s); return m.group(2)+m.group(1) if m else ""
def tipo(s):
    t=s.lower()
    if "impoq1" in t: return "IQ1"
    if "impoq2" in t: return "IQ2"
    if "expo" in t and "infoar" not in t: return "EXP"
    return None

def analyze(data):
    nl=0; hist=collections.Counter(); hi=0; fffd=0; crlf=0; d2=d4=iso=0; q_first=0; badq=0
    for line in data.split(b"\n"):
        if not line.strip(): continue
        nl+=1
        if line.endswith(b"\r"): crlf+=1; line=line[:-1]
        if any(c>127 for c in line): hi+=1
        if b"\xef\xbf\xbd" in line: fffd+=1
        if re_d2.search(line): d2+=1
        if re_d4.search(line): d4+=1
        if re_iso.search(line): iso+=1
        if line.startswith(b'"'): q_first+=1
        try:
            f=next(csv.reader([line.decode("latin-1")],delimiter="|",quotechar='"')); hist[len(f)]+=1
        except Exception: badq+=1
    top=hist.most_common(3)
    return [nl,len(data),";".join(f"{k}:{v}" for k,v in top),len(hist),hi,fffd,crlf,d2,d4,iso,q_first,badq]
rows=[]; rar=[]
z=zipfile.ZipFile(ZIP)
for i in z.infolist():
    n=i.filename
    if i.is_dir(): continue
    low=n.lower()
    if low.endswith(".rar"): rar.append(n); continue
    mm=re.search(r'z[rR]([0-9A-Za-z])\.txt$',n)
    if low.endswith(".zip"):
        t=tipo(n); p=per(n)
        if not t or p<"202401": continue
        try: inner=zipfile.ZipFile(io.BytesIO(z.read(i)))
        except Exception: rows.append([p,t,n.split("/")[-1],"<ZIP_INVALIDO>"]+[""]*12); continue
        for j in inner.infolist():
            m=re.search(r'z[rR]([0-9A-Za-z])\.txt$',j.filename)
            if j.is_dir() or not m: continue
            rows.append([p,t,"zip:"+n.split("/")[-1],"z"+m.group(1).upper()]+analyze(inner.read(j)))
    elif mm:
        t=tipo(n); p=per(n)
        if not t or p<"202401": continue
        rows.append([p,t,"suelto:"+"/".join(n.split("/")[-2:-1]),"z"+mm.group(1).upper()]+analyze(z.read(i)))
w=csv.writer(open(OUT,"w",newline=""))
w.writerow(["periodo","tipo","origen","archivo","lineas","bytes","campos_top3","n_distintos_campos","lineas_no_ascii","lineas_utf8_replacement","lineas_crlf","fechas_ddmmyy","fechas_ddmmyyyy","fechas_iso","lineas_con_comilla_inicial","lineas_csv_error"])
w.writerows(sorted(rows)); open(OUT+".rar.txt","w").write("\n".join(rar)); print("OK",len(rows),"archivos;",len(rar),"rar sin procesar")
