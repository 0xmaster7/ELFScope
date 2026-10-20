# Measured ELFScope results

Source commit: `6f06c1a4d054a6722f2cb7aaaf82c463b875463d`; date: 2026-10-20T09:03:41.769123+00:00
Environment: Linux-6.17.0-1022-azure-x86_64-with-glibc2.39; AMD EPYC 7763 64-Core Processor; g++ (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0; GNU readelf (GNU Binutils for Ubuntu) 2.42

One warmup parse; 15 samples of 20 file-open/read/parse iterations; steady_clock, microseconds per parse. Warm filesystem cache. Decimal MB/s = bytes / median microseconds. JSON serialization excluded.

Unchanged 14-file corpus: legacy 44696 checks plus 2 relationship fields per relocation (8862) and 3 explicit REL-null checks = 53561. RELA presence/type assertions strengthen existing checks without padding the denominator.

Validated 14 ELF files: 190 sections, 2328 symbols, 4431 relocations. Matched 53561/53561 supported-field comparisons against readelf (100.0%). Rejected 33 malformed files; link-check matched ld in 7/7 cases.

| Fixture | Bytes | Median µs | Min–max µs | MB/s |
|---|---:|---:|---:|---:|
| common.o | 968 | 9.12 | 8.91–124.57 | 106.13 |
| consumer.o | 1472 | 9.93 | 9.62–63.09 | 148.20 |
| duplicate.o | 1240 | 9.61 | 9.23–101.21 | 128.98 |
| main.o | 1360 | 10.34 | 9.65–112.47 | 131.52 |
| provider.o | 1272 | 10.04 | 9.61–91.28 | 126.65 |
| weak.o | 1552 | 10.03 | 9.68–113.01 | 154.79 |
| fixture.exe | 15952 | 19.47 | 18.63–123.75 | 819.17 |
| fixture.so | 15376 | 19.75 | 17.05–112.42 | 778.69 |
| stripped.o | 888 | 9.06 | 8.15–91.99 | 98.06 |
| medium.o | 30664 | 51.55 | 47.92–53.62 | 594.83 |
| large.o | 299864 | 859.79 | 754.64–1620.91 | 348.76 |
| structural_rel.o | 1472 | 9.92 | 9.70–11.47 | 148.37 |
| empty_symtab.o | 1472 | 8.63 | 8.55–10.27 | 170.53 |
| sectionless.o | 64 | 7.58 | 7.51–9.19 | 8.44 |

## Reproduction

`python3 benchmarks/benchmark.py build/elfscope` regenerates fixtures, checks all oracles, and measures. GCC, GNU binutils, Python 3, and a Release build are required. Raw timing samples and fixture SHA-256 digests are in results.json.

## Limitations

- Supported-field agreement is against GNU readelf, not a universal ELF correctness percentage.
- Link oracle uses ld -shared --no-undefined for seven supported cases, without implicit libraries.
- Structural REL/empty/sectionless fixtures supplement real compiler output; no claim that the REL fixture is ABI-linkable.
- Timings include file I/O with warm cache, not cold-storage throughput.
- 512 MiB input cap; ELF64 little-endian x86-64 only; extended ELF numbering rejected.
- Source commit identifies measured code; results are committed afterward.
