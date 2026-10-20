#!/usr/bin/env python3
"""GNU readelf/ld are external oracles. No parser-derived expected field values."""
import argparse, hashlib, json, os, pathlib, random, re, struct, subprocess, tempfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
ENV=dict(os.environ,LC_ALL='C')
def command(args,check=True): return subprocess.run([str(x) for x in args],capture_output=True,text=True,check=check,env=ENV)
def fixtures(directory,smoke=False):
    paths=[]
    for source in sorted((ROOT/'fixtures').glob('*.c')):
        path=directory/(source.stem+'.o')
        command(['gcc','-c','-O0','-fPIC','-fcommon' if source.stem=='common' else '-fno-common',source,'-o',path]);paths.append(path)
    executable=directory/'fixture.exe';command(['gcc',directory/'main.o',directory/'provider.o',directory/'consumer.o','-o',executable]);paths.append(executable)
    shared=directory/'fixture.so';command(['gcc','-shared',directory/'provider.o',directory/'consumer.o','-o',shared]);paths.append(shared)
    stripped=directory/'stripped.o';command(['objcopy','--strip-all',directory/'provider.o',stripped]);paths.append(stripped)
    for name,count in [('medium',80 if smoke else 200),('large',150 if smoke else 2000)]:
        source=directory/(name+'.c');source.write_text('extern int external(int);\n'+'\n'.join(f'int function_{i}(int x) {{ return external(x) + {i}; }}' for i in range(count)))
        path=directory/(name+'.o');command(['gcc','-c','-O0','-fPIC',source,'-o',path]);paths.append(path)
    # Structural REL fixture: compact the records of a compiler-generated RELA object.
    rel=bytearray((directory/'consumer.o').read_bytes());shoff=struct.unpack_from('<Q',rel,40)[0];shnum=struct.unpack_from('<H',rel,60)[0]
    empty_symbols=bytearray(rel)
    for n in range(shnum):
        at=shoff+n*64;kind=struct.unpack_from('<I',rel,at+4)[0]
        if kind==4:
            offset,size=struct.unpack_from('<QQ',rel,at+24);records=[bytes(rel[o:o+16]) for o in range(offset,offset+size,24)]
            compact=b''.join(records);rel[offset:offset+len(compact)]=compact
            struct.pack_into('<I',rel,at+4,9);struct.pack_into('<Q',rel,at+32,len(compact));struct.pack_into('<Q',rel,at+56,16)
            struct.pack_into('<Q',empty_symbols,at+32,0)
        if kind==2:
            struct.pack_into('<Q',empty_symbols,at+32,0);struct.pack_into('<I',empty_symbols,at+44,0)
    rel_path=directory/'structural_rel.o';rel_path.write_bytes(rel);paths.append(rel_path)
    empty_path=directory/'empty_symtab.o';empty_path.write_bytes(empty_symbols);paths.append(empty_path)
    # Valid sectionless ELF header: independently generated with documented ELF layout.
    empty=bytearray(64);empty[:7]=b'\x7fELF\x02\x01\x01';struct.pack_into('<HHI',empty,16,1,62,1);struct.pack_into('<H',empty,52,64)
    no_sections=directory/'sectionless.o';no_sections.write_bytes(empty);paths.append(no_sections)
    return paths

def reference(binary,path):
    data=json.loads(command([binary,'inspect',path,'--json']).stdout); checks=0
    def compare(actual,expected,field):
        nonlocal checks
        assert actual==expected,(path.name,field,actual,expected)
        checks+=1
    header=command(['readelf','-hW',path]).stdout
    def number(key):return int(re.search(re.escape(key)+r'\s*(\d+)',header)[1])
    for field,key in [('entry','Entry point address:')]:
        compare(data['header'][field],int(re.search(re.escape(key)+r'\s*(0x[0-9a-f]+)',header)[1],16),field)
    for field,key in [('shoff','Start of section headers:'),('phoff','Start of program headers:'),('ehsize','Size of this header:'),('phentsize','Size of program headers:'),('phnum','Number of program headers:'),('shentsize','Size of section headers:'),('shnum','Number of section headers:'),('shstrndx','Section header string table index:')]: compare(data['header'][field],number(key),field)
    compare(data['header']['class'],64 if 'ELF64' in header else 32,'class')
    compare(data['header']['encoding'],'little-endian' if "little endian" in header else 'big-endian','encoding')
    compare(data['header']['machine'],62 if 'Advanced Micro Devices X86-64' in header else -1,'machine')
    kind=re.search(r'Type:\s+(\S+)',header)[1];compare(data['header']['type'],{'REL':1,'EXEC':2,'DYN':3}[kind],'type')
    section_text=command(['readelf','-SW',path]).stdout
    section_rows=[]
    for line in section_text.splitlines():
        match=re.match(r'\s*\[\s*(\d+)\]\s+(.*)',line)
        if not match:continue
        index=int(match[1]);parts=match[2].split()
        if index==0:continue # NULL has no name; header count still independently checked.
        name,kind,address,offset,size,entsize=parts[:6];link,info,align=parts[-3:]
        section_rows.append(index);s=data['sections'][index]
        for key,expected in [('name',name),('address',int(address,16)),('offset',int(offset,16)),('size',int(size,16)),('entry_size',int(entsize,16)),('link',int(link)),('info',int(info)),('alignment',int(align))]: compare(s[key],expected,f'section[{index}].{key}')
    compare(len(section_rows),max(0,len(data['sections'])-1),'section row count')
    symbols=command(['readelf','-sW',path]).stdout;table=None;seen=0
    bindings={'LOCAL':0,'GLOBAL':1,'WEAK':2,'UNIQUE':10};types={'NOTYPE':0,'OBJECT':1,'FUNC':2,'SECTION':3,'FILE':4,'COMMON':5,'TLS':6,'IFUNC':10};vis={'DEFAULT':0,'INTERNAL':1,'HIDDEN':2,'PROTECTED':3}
    by_key={(s['table'],s['index']):s for s in data['symbols']}
    for line in symbols.splitlines():
        m=re.match(r"Symbol table '([^']+)' contains",line)
        if m:table=next(s['index'] for s in data['sections'] if s['name']==m[1]);continue
        m=re.match(r'\s*(\d+):\s+([0-9a-f]+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)(?:\s+(.*))?$',line)
        if not m:continue
        index,value,size,kind,binding,visibility,ndx,name=m.groups();s=by_key[(table,int(index))];seen+=1
        # readelf decorates dynamic names with symbol-version metadata; parser intentionally returns raw .dynstr names.
        name=(name or '').split(' (',1)[0]
        if data['sections'][table]['type']==11:name=name.split('@',1)[0]
        if kind=='SECTION':name='' # readelf synthesizes a section name when st_name==0.
        section={'UND':0,'ABS':65521,'COM':65522}.get(ndx)
        if section is None:section=int(ndx)
        for key,expected in [('name',name),('value',int(value,16)),('size',int(size)),('type',types[kind]),('binding',bindings[binding]),('visibility',vis[visibility]),('section',section)]:compare(s[key],expected,f'symbol[{table}:{index}].{key}')
    compare(len(data['symbols']),seen,'symbol row count')
    relocations=command(['readelf','-rW',path]).stdout;section=None;seen=0
    for line in relocations.splitlines():
        m=re.match(r"Relocation section '([^']+)'",line)
        if m:section=next(s['index'] for s in data['sections'] if s['name']==m[1]);continue
        m=re.match(r'\s*([0-9a-f]{8,16})\s+([0-9a-f]{8,16})\s+(\S+)\s*(.*)',line)
        if not m:continue
        offset,info,type_name,tail=m.groups();r=data['relocations'][seen];seen+=1;info=int(info,16)
        for key,expected in [('section',section),('offset',int(offset,16)),('symbol_index',info>>32),('type',info&0xffffffff)]:compare(r[key],expected,f'relocation[{seen}].{key}')
        if not r['type_name'].startswith('R_X86_64_UNKNOWN'):compare(r['type_name'],type_name,f'relocation[{seen}].type_name')
        # RELA signed addend, including relative relocations without a symbol value/name column.
        if r['addend'] is not None:
            m_add=re.search(r'([+-])\s+([0-9a-f]+)\s*$',tail)
            if m_add:expected=int(m_add[2],16)*(1 if m_add[1]=='+' else -1)
            elif r['type']==8:expected=int(tail.strip(),16)
            else:raise AssertionError(('unrecognized readelf addend',line))
            compare(r['addend'],expected,f'relocation[{seen}].addend')
    compare(len(data['relocations']),seen,'relocation row count')
    return data,checks

def malformed(binary,path,directory):
    original=path.read_bytes();shoff=struct.unpack_from('<Q',original,40)[0];shnum=struct.unpack_from('<H',original,60)[0]
    cases={}
    def change(name,offset,fmt,value):
        data=bytearray(original);struct.pack_into(fmt,data,offset,value);cases[name]=data
    for n in [0,1,4,16,32,63,len(original)-1]:cases[f'truncated_{n}']=original[:n]
    change('magic',0,'<I',0);change('class',4,'B',1);change('endian',5,'B',2);change('ident_version',6,'B',0);change('architecture',18,'<H',183)
    change('header_size',52,'<H',1);change('shoff_overflow',40,'<Q',2**64-16);change('oversized_count',60,'<H',65534);change('section_entry_size',58,'<H',1);change('shstr_index',62,'<H',shnum)
    change('extended_numbering',60,'<H',0);change('program_table',32,'<Q',2**64-1);cases.pop('program_table') # object has zero program headers; not a malformed table.
    sections=[]
    for n in range(shnum):
        at=shoff+n*64;kind=struct.unpack_from('<I',original,at+4)[0];sections.append((n,at,kind))
    _,symat,_=next(s for s in sections if s[2]==2);symoff=struct.unpack_from('<Q',original,symat+24)[0]
    change('symbol_link',symat+40,'<I',shnum);change('symbol_entry_size',symat+56,'<Q',1);change('symbol_name',symoff+24,'<I',2**32-1);change('symbol_section',symoff+24+6,'<H',shnum)
    _,relat,_=next(s for s in sections if s[2]==4);reloff=struct.unpack_from('<Q',original,relat+24)[0]
    change('relocation_link',relat+40,'<I',shnum);change('relocation_target',relat+44,'<I',shnum);change('relocation_symbol',reloff+8,'<Q',(2**32-1)<<32);change('relocation_size',relat+32,'<Q',1)
    change('section_range',sections[1][1]+24,'<Q',2**64-1)
    shstr=struct.unpack_from('<H',original,62)[0];strat=shoff+64*shstr;stroff,strsize=struct.unpack_from('<QQ',original,strat+24)
    data=bytearray(original);data[stroff:stroff+strsize]=b'x'*strsize;cases['unterminated_strings']=data
    for name,data in cases.items():
        broken=directory/'broken.elf';broken.write_bytes(data)
        result=command([binary,'inspect',broken,'--json'],check=False)
        assert result.returncode==1,(name,result.returncode,result.stdout,result.stderr)
        assert 'AddressSanitizer' not in result.stderr and 'runtime error:' not in result.stderr,(name,result.stderr)
    return len(cases)

def mutations(binary,path,directory):
    rng=random.Random(481516);original=path.read_bytes();counts={'accepted':0,'rejected':0,'seed':481516}
    for _ in range(128):
        data=bytearray(original)
        for _ in range(rng.randrange(1,6)):
            at=rng.randrange(len(data));data[at]^=rng.randrange(1,256)
        if rng.randrange(4)==0:data=data[:rng.randrange(len(data))]
        mutated=directory/'mutation.elf';mutated.write_bytes(data);result=command([binary,'inspect',mutated,'--json'],check=False)
        assert result.returncode in [0,1],(result.returncode,result.stderr)
        assert 'AddressSanitizer' not in result.stderr and 'runtime error:' not in result.stderr,result.stderr
        if result.returncode==0:
            json.loads(result.stdout);counts['accepted']+=1
        else:counts['rejected']+=1
    return counts

def link_cases(binary,directory):
    tests=[('resolved',['provider','consumer'],True),('unresolved',['consumer'],False),('duplicate',['provider','duplicate'],False),('weak_override',['provider','weak','consumer'],True),('weak_only',['weak'],True),('common_override',['provider','common','consumer'],True),('common_merge',['common','common'],True)]
    for name,names,expected in tests:
        objects=[directory/(n+'.o') for n in names];result=command([binary,'link-check',*objects],check=False);data=json.loads(result.stdout)
        predicted=result.returncode==0;assert data['has_errors']==(not predicted)
        # Fully resolve object-set references, allowing undefined weak symbols, without startup/runtime libraries.
        linked=command(['ld','-shared','--no-undefined','-o',directory/'linked.so',*objects],check=False).returncode==0
        assert predicted==linked==expected,(name,result.stdout,linked)
    return len(tests)

def validate(binary,directory,smoke=False):
    paths=fixtures(directory,smoke);rows=[];checks=0
    for path in paths:
        data,count=reference(binary,path);checks+=count
        rows.append({'fixture':path.name,'bytes':data['file_bytes'],'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'sections':len(data['sections']),'symbols':len(data['symbols']),'relocations':len(data['relocations']),'reference_comparisons':count})
    rejected=malformed(binary,directory/'consumer.o',directory);links=link_cases(binary,directory)
    fuzz=mutations(binary,directory/'consumer.o',directory)
    # All public presentation commands execute production parser paths.
    for cmd in ['inspect','sections','symbols','relocations']:assert command([binary,cmd,directory/'consumer.o']).stdout
    return {'elf_files_tested':len(paths),'sections_parsed':sum(r['sections'] for r in rows),'symbols_parsed':sum(r['symbols'] for r in rows),'relocations_parsed':sum(r['relocations'] for r in rows),'readelf_comparisons':checks,'matching_comparisons':checks,'supported_field_agreement_pct':100.0,'malformed_inputs_rejected':rejected,'link_cases_matching_ld':links,'link_cases_total':links,'failures':0,'mutation_robustness':fuzz,'files':rows},paths
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('binary');p.add_argument('--smoke',action='store_true');a=p.parse_args()
    with tempfile.TemporaryDirectory() as d:
        result,_=validate(str(pathlib.Path(a.binary).resolve()),pathlib.Path(d),a.smoke)
        print(json.dumps(result,indent=2))
