import re,sys,os
AUTHOR=sys.argv[1] if len(sys.argv)>1 else "Belloc"
WRITE="--write" in sys.argv
base=f"VaultEnglish/Authors/{AUTHOR}/Atomized"
BROKEN=re.compile(r'\[\[L(\d{1,3})[|\]>»】\)]([^\]\[]*?)\]{1,2}')
def en_links(b): return [m.group(1) for m in re.finditer(r'\[\[([^\]\[]+?)\]\]',b)]
stat={"files":0,"fix":0,"unres":0}; unresfiles=[]
for dp,_,fs in os.walk(base):
    for f in fs:
        if not f.endswith('.it.md'): continue
        ip=os.path.join(dp,f); ep=ip[:-6]+".md"
        it=open(ip,encoding="utf-8").read()
        if '[[L' not in it: continue
        if not os.path.exists(ep): continue
        en=open(ep,encoding="utf-8").read()
        eb=re.split(r'\n\s*\n',en); ib=re.split(r'\n\s*\n',it)
        changed=False; fu=0
        for i,b in enumerate(ib):
            if '[[L' not in b: continue
            links=en_links(eb[i]) if i<len(eb) else []
            def repl(m):
                n=int(m.group(1)); s=m.group(2).strip()
                if 1<=n<=len(links):
                    stat["fix"]+=1; return f"[[{links[n-1].split('|')[0]}|{s}]]"
                stat["unres"]+=1
                return m.group(0)
            nb=BROKEN.sub(repl,b)
            if nb!=b: ib[i]=nb; changed=True
        # conta eventuali Lxx rimasti dopo il fix (unresolvable)
        joined="\n\n".join(ib)
        left=re.findall(r'\[\[L\d{1,3}[|\]]',joined)
        if changed:
            stat["files"]+=1
            rel=os.path.relpath(ip,base)
            print(f"  {rel[:58]:58} {'RESIDUI!' if left else 'ok'}")
            if left: unresfiles.append((rel,left))
            if WRITE: open(ip,"w",encoding="utf-8").write(joined)
print(f"\nAUTORE={AUTHOR}  file toccati={stat['files']}  token riparati={stat['fix']}  non-risolvibili={stat['unres']}")
if unresfiles:
    print("FILE CON RESIDUI (fuori-range, da guardare a mano):")
    for r,l in unresfiles: print("   ",r,l)
print("MODE:", "SCRITTO" if WRITE else "DRY-RUN")
