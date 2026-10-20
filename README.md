# ELFScope

A C++17 ELF inspector and static object-set symbol-resolution checker. It reads actual ELF bytes and exposes the relationships between sections, symbols, and relocations that a linker uses. The link checker is a bounded model, with GNU `ld` as an external validation oracle.

## Build and use

Requires Linux x86-64, a C++17 compiler, CMake, Python 3, GCC, and GNU binutils for reference tests.

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j2
ctest --test-dir build --output-on-failure
cc -c -fPIC fixtures/consumer.c -o build/consumer.o
cc -c -fPIC fixtures/provider.c -o build/provider.o
build/elfscope inspect build/consumer.o
build/elfscope sections build/consumer.o
build/elfscope symbols build/consumer.o
build/elfscope relocations build/consumer.o
build/elfscope inspect build/consumer.o --json
build/elfscope link-check build/consumer.o build/provider.o
python3 benchmarks/benchmark.py build/elfscope
```

Configure a separate Debug build with `-DENABLE_SANITIZERS=ON` for ASan/UBSan. CI checks both Release and sanitized Debug builds. `link-check` always prints JSON and exits 2 for duplicate strong definitions or active unresolved nonweak references within the supplied object set; malformed/unsupported input exits 1. Other commands accept `--json`, returning the full inspect schema.

Example captured from the commands above (GCC 13.3, Linux x86-64):

```text
ELF64 little-endian x86-64 type=1 bytes=1472
sections=13 symbols=7 relocations=3
```

`relocations` includes the `shared_value` GOT-relative reference at offset 11 and the `square` PLT-relative reference at offset 20, both with explicit addend -4. Exact layout depends on the compiler.

## Supported data

- ELF64 little-endian x86-64 relocatable objects, executables, and shared objects.
- Header metadata and validated section/program-header table extents.
- Section names, types, flags, addresses, offsets, sizes, links, and alignment.
- Static and dynamic symbol tables, including binding, type, visibility, definition status, value, size, and section index.
- REL/RELA offsets, numeric and named relocation types, symbol table/index, target section, and explicit signed addends. REL implicit addends remain `null` because they are not decoded from target bytes.
- Global/weak definitions and references, duplicate strong definitions, strong-over-common-over-weak selection, and merging common definitions by largest size. Undefined declarations remain visible in `references`, with `active` and `requires_definition` flags. An active use is any matching relocation, including R_X86_64_NONE (GNU ld still resolves its symbol); unused declarations report `unused_undefined_declaration` without a fatal error. Unknown relocation types conservatively count as uses. Unresolved weak symbols are optional; `_GLOBAL_OFFSET_TABLE_` is identified as linker-synthesized.

Unknown relocation types retain their numeric values. Non-ASCII name bytes are JSON-escaped as U+00xx, preserving byte values rather than assuming UTF-8.

## Architecture and defensive parsing

`include/elfscope.hpp` defines value-type results. `src/elfscope.cpp` implements a byte reader, validation, JSON serialization, and symbol-resolution analysis. `src/main.cpp` handles presentation and benchmarking. File streams and containers use RAII; integers are assembled explicitly from little-endian bytes. No file data is reinterpreted as a native ELF structure.

Every read checks `offset <= length` and `size <= length - offset`; multiplication is checked before computing table extents. Headers and table entry sizes, string offsets/terminators, symbol section indices, null-symbol records, string-table boundary NUL bytes, symbol-table links, relocation links/targets/symbol indices, relocatable target offsets, and record divisibility are validated. Input files are capped at 512 MiB. Extended ELF numbering and extended symbol section indices are rejected explicitly. Sectionless files and empty/missing symbol tables are valid.

## Tests and benchmarks

```sh
python3 tests/test.py build/elfscope
python3 benchmarks/benchmark.py build/elfscope --smoke
```

Fixtures are compiled from committed C sources. Additional generated C sources produce medium/large objects; executable, shared, and stripped outputs cover different table combinations. Three structural fixtures exercise REL records, empty symbol tables, and a sectionless ELF header; these are documented additions to real compiler output, not ABI-linkability claims.

The independent oracle is GNU `readelf -hW -SW -sW -rW`. The harness compares numeric header fields; section names, types, addresses, offsets, sizes, entry sizes, links, info and alignment; symbol names, values, sizes, types, bindings, visibility and section indices; relocation offsets, types, symbol indices, relocation sections and explicit addends. It normalizes readelf's synthesized SECTION symbol names and dynamic symbol-version decorations. RELA addend presence and signed values are required from readelf section types; REL implicit addends must remain null. Relocation target sections, symbol tables, and the documented named/unknown type representation are checked independently of analyzer output. Each field comparison contributes once to the denominator. The original 44,696 checks become 53,561 on the unchanged 14-file corpus: 8,862 additional relationship checks and three REL-null checks. Section/symbol/relocation row counts are checked too.

Seven original object-set cases are compared with `ld -shared --no-undefined`. Benchmarks also execute the targeted gates. A separate `audit_regressions` CTest group adds eleven linker cases (including unused declarations, active/weak/NONE/GOT references and precedence) and fifteen deliberate JSON corruptions which the reference oracle must reject. Malformed fixtures cover truncated headers/tables, bad magic/class/endianness/architecture, invalid sizes/counts/offsets, unterminated strings, and invalid symbol/relocation references. A fixed-seed 128-case mutation corpus checks rejection or successful JSON output without crashes; accepted mutations are not counted as malformed rejections or correctness proofs.

Actual counts, per-size latency medians, variability, fixture digests, environment, and raw timing samples: [benchmarks/results.md](benchmarks/results.md) and [results.json](benchmarks/results.json). The benchmark includes warm-cache file reads and parsing, excludes JSON output, uses a warmup plus 15 batches of 20 iterations, and reports decimal MB/s. No flaky timing threshold is used in CI.

## Limitations

This is not a linker. There is no relocation application, archive extraction, COMDAT/group selection, shared-library lookup, symbol-version resolution, dynamic loading, linker scripts, TLS layout, visibility/interposition model, or full GNU special-symbol behavior. Only `_GLOBAL_OFFSET_TABLE_` has explicit synthesized-symbol handling. Link-check requires relocatable files and LOCAL/GLOBAL/WEAK bindings; unsupported bindings are rejected. Selection reports are diagnostic and do not implement complete common-symbol alignment/layout rules. Unresolved references mean unresolved **within the provided objects**, and may be resolved by omitted libraries.

Program-header table bounds are checked, but segment contents are not analyzed. The parser does not validate every ABI constraint or compressed section payload. Parsing acceptance does not imply a binary is safe to execute. Extended numbering is outside the supported subset.

References: [System V ELF gABI](https://gabi.xinuos.com/elf/), [x86-64 psABI](https://gitlab.com/x86-psABIs/x86-64-ABI), [GNU readelf](https://sourceware.org/binutils/docs/binutils/readelf.html), [GNU ld](https://sourceware.org/binutils/docs/ld/).
