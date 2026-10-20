#include "elfscope.hpp"
#include <iostream>
#include <stdexcept>
#include <vector>
void check(bool b) {
  if (!b)
    throw std::runtime_error("unit assertion failed");
}
int main() {
  std::vector<std::uint8_t> bytes(64, 0);
  bytes[0] = 127;
  bytes[1] = 'E';
  bytes[2] = 'L';
  bytes[3] = 'F';
  bytes[4] = 2;
  bytes[5] = 1;
  bytes[6] = 1;
  bytes[16] = 1;
  bytes[18] = 62;
  bytes[20] = 1;
  bytes[52] = 64;
  auto f = elfscope::parse_bytes(bytes);
  check(f.sections.empty());
  check(f.header.machine == 62);
  check(elfscope::quote("a\n\"\\") == "\"a\\u000a\\\"\\\\\"");
  for (std::size_t n = 0; n < 64; ++n) {
    bool rejected = false;
    try {
      (void)elfscope::parse_bytes(std::vector<std::uint8_t>(
          bytes.begin(), bytes.begin() + static_cast<std::ptrdiff_t>(n)));
    } catch (const std::exception &) {
      rejected = true;
    }
    check(rejected);
  }
  bytes[5] = 2;
  bool rejected = false;
  try {
    (void)elfscope::parse_bytes(bytes);
  } catch (const std::exception &) {
    rejected = true;
  }
  check(rejected);
  std::cout << "bounds, header, and JSON unit assertions passed\n";
}
