#pragma once
#include <cstdint>
#include <string>
#include <vector>
namespace elfscope {
struct Header {
  std::uint16_t type = 0, machine = 0, ehsize = 0, phentsize = 0, phnum = 0,
                shentsize = 0, shnum = 0, shstrndx = 0;
  std::uint32_t version = 0, flags = 0;
  std::uint64_t entry = 0, phoff = 0, shoff = 0;
};
struct Section {
  std::string name;
  std::uint32_t name_offset = 0, type = 0, link = 0, info = 0;
  std::uint64_t flags = 0, address = 0, offset = 0, size = 0, alignment = 0,
                entry_size = 0;
};
struct Symbol {
  std::string name;
  std::size_t table = 0, index = 0;
  std::uint64_t value = 0, size = 0;
  std::uint16_t section = 0;
  std::uint8_t binding = 0, type = 0, visibility = 0;
};
struct Relocation {
  std::size_t section = 0, target = 0, symbol_table = 0, symbol_index = 0;
  std::uint64_t offset = 0;
  std::uint32_t type = 0;
  bool has_addend = false;
  std::int64_t addend = 0;
  std::string symbol;
};
struct File {
  std::string path;
  std::size_t bytes = 0;
  Header header;
  std::vector<Section> sections;
  std::vector<Symbol> symbols;
  std::vector<Relocation> relocations;
};
File parse(const std::string &path);
File parse_bytes(const std::vector<std::uint8_t> &bytes,
                 const std::string &path = "<memory>");
std::string json(const File &file);
std::string quote(const std::string &s);
std::string relocation_name(std::uint32_t type);
struct LinkReport {
  std::string json;
  bool has_errors = false;
};
LinkReport link_check(const std::vector<File> &files);
} // namespace elfscope
