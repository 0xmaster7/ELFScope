#!/usr/bin/env python3
import argparse, datetime, json, pathlib, platform, subprocess, sys, tempfile
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tests'))
from test import validate
from remediation import validate as validate_regressions

def output(*args):return subprocess.check_output(args,text=True,cwd=ROOT).strip()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('binary');parser.add_argument('--smoke',action='store_true');args=parser.parse_args();binary=str(pathlib.Path(args.binary).resolve())
    with tempfile.TemporaryDirectory() as temp:
        correctness,paths=validate(binary,pathlib.Path(temp),args.smoke); regressions=validate_regressions(binary)
        timing=[]
        for path in paths:
            row=json.loads(output(binary,'benchmark',str(path)));row['fixture']=path.name;timing.append(row)
        if args.smoke:
            assert all(r['latency_us_median']>0 for r in timing);print('benchmark smoke and reference validation passed');return
        data={'source_commit':output('git','rev-parse','HEAD'),'date_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'os':platform.platform(),
              'cpu':next(l.split(':',1)[1].strip() for l in pathlib.Path('/proc/cpuinfo').read_text().splitlines() if l.startswith('model name')),
              'compiler':output('g++','--version').splitlines()[0],'reference':output('readelf','--version').splitlines()[0],'build':'CMake Release; GCC; -O3 -DNDEBUG',
              'method':'One warmup parse; 15 samples of 20 file-open/read/parse iterations; steady_clock, microseconds per parse. Warm filesystem cache. Decimal MB/s = bytes / median microseconds. JSON serialization excluded.',
              'comparison_denominator_change':'Unchanged 14-file corpus: legacy 44696 checks plus 2 relationship fields per relocation (8862) and 3 explicit REL-null checks = 53561. RELA presence/type assertions strengthen existing checks without padding the denominator.',
              'fixture_generation':'GCC -O0 -fPIC; large=2000 functions, medium=200; fixture ELF executable/shared library; objcopy-stripped object; documented structural REL, empty symtab, and sectionless fixtures.',
              'audit_regressions':regressions,'correctness':correctness,'timings':timing,'limitations':['Supported-field agreement is against GNU readelf, not a universal ELF correctness percentage.','Link oracle uses ld -shared --no-undefined for seven supported cases, without implicit libraries.','Structural REL/empty/sectionless fixtures supplement real compiler output; no claim that the REL fixture is ABI-linkable.','Timings include file I/O with warm cache, not cold-storage throughput.','512 MiB input cap; ELF64 little-endian x86-64 only; extended ELF numbering rejected.','Source commit identifies measured code; results are committed afterward.']}
        (ROOT/'benchmarks/results.json').write_text(json.dumps(data,indent=2)+'\n')
        c=correctness
        lines=['# Measured ELFScope results','',f"Source commit: `{data['source_commit']}`; date: {data['date_utc']}",f"Environment: {data['os']}; {data['cpu']}; {data['compiler']}; {data['reference']}",'',data['method'],'',data['comparison_denominator_change'],'',f"Validated {c['elf_files_tested']} ELF files: {c['sections_parsed']} sections, {c['symbols_parsed']} symbols, {c['relocations_parsed']} relocations. Matched {c['matching_comparisons']}/{c['readelf_comparisons']} supported-field comparisons against readelf ({c['supported_field_agreement_pct']:.1f}%). Rejected {c['malformed_inputs_rejected']} malformed files; link-check matched ld in {c['link_cases_matching_ld']}/{c['link_cases_total']} cases.",'','| Fixture | Bytes | Median µs | Min–max µs | MB/s |','|---|---:|---:|---:|---:|']
        for r in timing:lines.append(f"| {r['fixture']} | {r['file_bytes']} | {r['latency_us_median']:.2f} | {r['latency_us_min']:.2f}–{r['latency_us_max']:.2f} | {r['throughput_MB_s']:.2f} |")
        lines+=['','## Reproduction','','`python3 benchmarks/benchmark.py build/elfscope` regenerates fixtures, checks all oracles, and measures. GCC, GNU binutils, Python 3, and a Release build are required. Raw timing samples and fixture SHA-256 digests are in results.json.','','## Limitations','']+['- '+s for s in data['limitations']]
        (ROOT/'benchmarks/results.md').write_text('\n'.join(lines)+'\n');print(json.dumps({k:v for k,v in correctness.items() if k!='files'}))
if __name__=='__main__':main()
