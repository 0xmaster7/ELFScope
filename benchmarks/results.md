# Measured ELFScope results

Source commit: `b275ef4ebd78b3304ed608f5098877b3a0051ce2`; date: 2026-10-20T08:04:32.915333+00:00
Environment: Linux-6.17.0-1022-azure-x86_64-with-glibc2.39; AMD EPYC 7763 64-Core Processor; g++ (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0; GNU readelf (GNU Binutils for Ubuntu) 2.42

One warmup parse; 15 samples of 20 file-open/read/parse iterations; steady_clock, microseconds per parse. Warm filesystem cache. Decimal MB/s = bytes / median microseconds. JSON serialization excluded.

Validated 14 ELF files: 190 sections, 2328 symbols, 4431 relocations. Matched 44519/44519 supported-field comparisons against readelf (100.0%). Rejected 28 malformed files; link-check matched ld in 7/7 cases.

| Fixture | Bytes | Median µs | Min–max µs | MB/s |
|---|---:|---:|---:|---:|
| common.o | 968 | 5.87 | 5.84–13.10 | 164.91 |
| consumer.o | 1472 | 6.46 | 6.43–8.62 | 227.91 |
| duplicate.o | 1240 | 6.10 | 6.07–8.18 | 203.42 |
| main.o | 1360 | 6.34 | 6.32–8.40 | 214.57 |
| provider.o | 1272 | 9.30 | 6.15–13.50 | 136.73 |
| weak.o | 1552 | 7.58 | 6.47–12.12 | 204.84 |
| fixture.exe | 15952 | 11.89 | 11.59–15.94 | 1341.38 |
| fixture.so | 15376 | 11.15 | 10.92–13.68 | 1378.54 |
| stripped.o | 888 | 5.51 | 5.49–7.24 | 161.25 |
| medium.o | 30664 | 27.49 | 26.07–31.94 | 1115.26 |
| large.o | 299864 | 521.99 | 511.90–604.54 | 574.47 |
| structural_rel.o | 1472 | 6.48 | 6.47–8.42 | 227.12 |
| empty_symtab.o | 1472 | 5.75 | 5.72–7.25 | 256.14 |
| sectionless.o | 64 | 4.86 | 4.85–9.39 | 13.17 |

## Reproduction

`python3 benchmarks/benchmark.py build/elfscope` regenerates fixtures, checks all oracles, and measures. GCC, GNU binutils, Python 3, and a Release build are required. Raw timing samples and fixture SHA-256 digests are in results.json.

## Limitations

- Supported-field agreement is against GNU readelf, not a universal ELF correctness percentage.
- Link oracle uses ld -shared --no-undefined for seven supported cases, without implicit libraries.
- Structural REL/empty/sectionless fixtures supplement real compiler output; no claim that the REL fixture is ABI-linkable.
- Timings include file I/O with warm cache, not cold-storage throughput.
- 512 MiB input cap; ELF64 little-endian x86-64 only; extended ELF numbering rejected.
- Source commit identifies measured code; results are committed afterward.
