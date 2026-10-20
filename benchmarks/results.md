# Measured ELFScope results

Source commit: `d444bed0377ab46804941edbbd61a209b16ae1ca`; date: 2026-10-20T08:19:56.370241+00:00
Environment: Linux-6.17.0-1022-azure-x86_64-with-glibc2.39; AMD EPYC 7763 64-Core Processor; g++ (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0; GNU readelf (GNU Binutils for Ubuntu) 2.42

One warmup parse; 15 samples of 20 file-open/read/parse iterations; steady_clock, microseconds per parse. Warm filesystem cache. Decimal MB/s = bytes / median microseconds. JSON serialization excluded.

Validated 14 ELF files: 190 sections, 2328 symbols, 4431 relocations. Matched 44696/44696 supported-field comparisons against readelf (100.0%). Rejected 33 malformed files; link-check matched ld in 7/7 cases.

| Fixture | Bytes | Median µs | Min–max µs | MB/s |
|---|---:|---:|---:|---:|
| common.o | 968 | 6.05 | 6.02–7.41 | 160.03 |
| consumer.o | 1472 | 6.65 | 6.63–8.24 | 221.29 |
| duplicate.o | 1240 | 6.26 | 6.23–9.16 | 198.24 |
| main.o | 1360 | 6.43 | 6.41–8.61 | 211.66 |
| provider.o | 1272 | 6.66 | 6.32–8.02 | 190.88 |
| weak.o | 1552 | 6.65 | 6.63–9.75 | 233.42 |
| fixture.exe | 15952 | 12.19 | 11.93–15.17 | 1308.10 |
| fixture.so | 15376 | 11.02 | 10.91–12.78 | 1395.46 |
| stripped.o | 888 | 5.84 | 5.70–10.13 | 151.95 |
| medium.o | 30664 | 28.13 | 26.91–30.45 | 1090.20 |
| large.o | 299864 | 538.07 | 524.56–655.05 | 557.30 |
| structural_rel.o | 1472 | 7.89 | 7.40–8.90 | 186.57 |
| empty_symtab.o | 1472 | 6.16 | 6.13–8.66 | 239.11 |
| sectionless.o | 64 | 5.67 | 5.47–6.50 | 11.29 |

## Reproduction

`python3 benchmarks/benchmark.py build/elfscope` regenerates fixtures, checks all oracles, and measures. GCC, GNU binutils, Python 3, and a Release build are required. Raw timing samples and fixture SHA-256 digests are in results.json.

## Limitations

- Supported-field agreement is against GNU readelf, not a universal ELF correctness percentage.
- Link oracle uses ld -shared --no-undefined for seven supported cases, without implicit libraries.
- Structural REL/empty/sectionless fixtures supplement real compiler output; no claim that the REL fixture is ABI-linkable.
- Timings include file I/O with warm cache, not cold-storage throughput.
- 512 MiB input cap; ELF64 little-endian x86-64 only; extended ELF numbering rejected.
- Source commit identifies measured code; results are committed afterward.
