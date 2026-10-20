#include "elfscope.hpp"
#include <algorithm>
#include <fstream>
#include <iomanip>
#include <limits>
#include <map>
#include <sstream>
#include <stdexcept>
namespace elfscope {
namespace {
class Reader {
    const std::vector<std::uint8_t>& data;
public:
    explicit Reader(const std::vector<std::uint8_t>& d):data(d){}
    void range(std::uint64_t offset,std::uint64_t size) const {
        if(offset>data.size() || size>data.size()-offset) throw std::runtime_error("range outside file");
    }
    void table(std::uint64_t offset,std::uint64_t count,std::uint64_t entry) const {
        if(entry && count>std::numeric_limits<std::uint64_t>::max()/entry) throw std::runtime_error("table size overflow");
        range(offset,count*entry);
    }
    std::uint64_t u(std::uint64_t offset,unsigned width) const {
        range(offset,width); std::uint64_t result=0;
        for(unsigned i=0;i<width;++i) result|=static_cast<std::uint64_t>(data[static_cast<std::size_t>(offset+i)])<<(i*8U);
        return result;
    }
    std::uint16_t u16(std::uint64_t o) const { return static_cast<std::uint16_t>(u(o,2)); }
    std::uint32_t u32(std::uint64_t o) const { return static_cast<std::uint32_t>(u(o,4)); }
    std::string string(const Section& table,std::uint64_t index) const {
        if(table.type!=3 || index>=table.size) throw std::runtime_error("invalid string-table reference");
        range(table.offset,table.size);
        const auto begin=data.begin()+static_cast<std::ptrdiff_t>(table.offset+index);
        const auto end=data.begin()+static_cast<std::ptrdiff_t>(table.offset+table.size);
        auto nul=std::find(begin,end,0); if(nul==end) throw std::runtime_error("unterminated string-table entry");
        return std::string(begin,nul);
    }
};
std::int64_t signed64(std::uint64_t x) {
    if(x<=static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max())) return static_cast<std::int64_t>(x);
    return -1-static_cast<std::int64_t>(std::numeric_limits<std::uint64_t>::max()-x);
}
}
std::string quote(const std::string& s) {
    std::ostringstream o; o<<'"';
    for(unsigned char c:s) {
        if(c=='"' || c=='\\') o<<'\\'<<static_cast<char>(c);
        else if(c<32 || c>=127) o<<"\\u00"<<std::hex<<std::setw(2)<<std::setfill('0')<<static_cast<unsigned>(c)<<std::dec;
        else o<<static_cast<char>(c);
    }
    o<<'"'; return o.str();
}
File parse(const std::string& path) {
    std::ifstream in(path,std::ios::binary|std::ios::ate); if(!in) throw std::runtime_error("cannot open file: "+path);
    const auto length=in.tellg();
    constexpr std::uint64_t max_file=512ULL*1024*1024;
    if(length<0 || static_cast<std::uint64_t>(length)>max_file) throw std::runtime_error("file exceeds 512 MiB limit");
    std::vector<std::uint8_t> bytes(static_cast<std::size_t>(length)); in.seekg(0);
    if(!bytes.empty() && !in.read(reinterpret_cast<char*>(bytes.data()),static_cast<std::streamsize>(bytes.size()))) throw std::runtime_error("file read failed");
    return parse_bytes(bytes,path);
}
File parse_bytes(const std::vector<std::uint8_t>& bytes,const std::string& path) {
    Reader r(bytes);r.range(0,64);
    if(r.u(0,4)!=0x464c457f) throw std::runtime_error("invalid ELF magic");
    if(r.u(4,1)!=2) throw std::runtime_error("unsupported ELF class (ELF64 required)");
    if(r.u(5,1)!=1) throw std::runtime_error("unsupported encoding (little-endian required)");
    if(r.u(6,1)!=1) throw std::runtime_error("unsupported ELF identification version");
    File f;f.path=path;f.bytes=bytes.size();auto& h=f.header;
    h.type=r.u16(16);h.machine=r.u16(18);h.version=r.u32(20);h.entry=r.u(24,8);h.phoff=r.u(32,8);h.shoff=r.u(40,8);h.flags=r.u32(48);
    h.ehsize=r.u16(52);h.phentsize=r.u16(54);h.phnum=r.u16(56);h.shentsize=r.u16(58);h.shnum=r.u16(60);h.shstrndx=r.u16(62);
    if(h.machine!=62) throw std::runtime_error("unsupported architecture (x86-64 required)");
    if(h.type<1 || h.type>3) throw std::runtime_error("unsupported file type (REL/EXEC/DYN required)");
    if(h.version!=1 || h.ehsize!=64) throw std::runtime_error("invalid ELF header version/size");
    if(h.phnum==65535 || h.shstrndx==65535 || (h.shnum==0 && h.shoff!=0)) throw std::runtime_error("unsupported extended ELF numbering");
    if(h.phnum) { if(h.phentsize!=56) throw std::runtime_error("invalid program-header entry size"); r.table(h.phoff,h.phnum,h.phentsize); }
    if(h.shnum==0) { if(h.shstrndx!=0) throw std::runtime_error("section-name index without sections"); return f; }
    if(h.shoff<64 || h.shentsize!=64) throw std::runtime_error("invalid section-header table");
    r.table(h.shoff,h.shnum,h.shentsize);
    if(h.shstrndx>=h.shnum) throw std::runtime_error("invalid section-name table index");
    for(std::uint64_t n=0;n<h.shnum;++n) {
        auto at=h.shoff+n*64;Section s;
        s.name_offset=r.u32(at);s.type=r.u32(at+4);s.flags=r.u(at+8,8);s.address=r.u(at+16,8);s.offset=r.u(at+24,8);s.size=r.u(at+32,8);
        s.link=r.u32(at+40);s.info=r.u32(at+44);s.alignment=r.u(at+48,8);s.entry_size=r.u(at+56,8);
        if(s.type!=0 && s.type!=8) r.range(s.offset,s.size);
        if(s.alignment && (s.alignment&(s.alignment-1))) throw std::runtime_error("invalid section alignment");
        f.sections.push_back(s);
    }
    if(f.sections[0].type!=0) throw std::runtime_error("section zero must be NULL");
    if(h.shstrndx!=0) for(auto& s:f.sections) s.name=r.string(f.sections[h.shstrndx],s.name_offset);
    else for(const auto& s:f.sections) if(s.name_offset!=0) throw std::runtime_error("named section without string table");
    std::map<std::size_t,std::vector<Symbol>> tables;
    for(std::size_t index=0;index<f.sections.size();++index) {
        const auto& s=f.sections[index]; if(s.type!=2 && s.type!=11) continue;
        if(s.entry_size!=24 || s.size%24 || s.link>=f.sections.size()) throw std::runtime_error("invalid symbol table");
        const auto& strings=f.sections[s.link]; if(strings.type!=3) throw std::runtime_error("symbol table does not link to STRTAB");
        if(s.info>s.size/24) throw std::runtime_error("invalid symbol-table local boundary");
        auto& symbols=tables[index];
        for(std::uint64_t n=0;n<s.size/24;++n) {
            auto at=s.offset+n*24;Symbol sym;sym.table=index;sym.index=static_cast<std::size_t>(n);
            sym.name=r.string(strings,r.u32(at));auto info=r.u(at+4,1);sym.binding=static_cast<std::uint8_t>(info>>4U);sym.type=static_cast<std::uint8_t>(info&15U);
            sym.visibility=static_cast<std::uint8_t>(r.u(at+5,1)&3U);sym.section=r.u16(at+6);sym.value=r.u(at+8,8);sym.size=r.u(at+16,8);
            if(sym.section==65535) throw std::runtime_error("unsupported extended symbol section index");
            if(sym.section<65280 && sym.section>=f.sections.size()) throw std::runtime_error("invalid symbol section index");
            symbols.push_back(sym);f.symbols.push_back(sym);
        }
    }
    for(std::size_t index=0;index<f.sections.size();++index) {
        const auto& s=f.sections[index]; if(s.type!=4 && s.type!=9) continue;
        const std::uint64_t width=s.type==4?24:16;
        if(s.entry_size!=width || s.size%width || !tables.count(s.link) || s.info>=f.sections.size() || (h.type==1 && s.info==0)) throw std::runtime_error("invalid relocation table relationship");
        const auto& symbols=tables.at(s.link);
        for(std::uint64_t n=0;n<s.size/width;++n) {
            auto at=s.offset+n*width;auto info=r.u(at+8,8);auto sym=info>>32U;
            if(sym>=symbols.size()) throw std::runtime_error("invalid relocation symbol index");
            Relocation rel;rel.section=index;rel.target=s.info;rel.symbol_table=s.link;rel.symbol_index=static_cast<std::size_t>(sym);rel.offset=r.u(at,8);
            rel.type=static_cast<std::uint32_t>(info&0xffffffffULL);rel.symbol=symbols[rel.symbol_index].name;rel.has_addend=s.type==4;
            if(rel.has_addend) rel.addend=signed64(r.u(at+16,8));
            f.relocations.push_back(rel);
        }
    }
    return f;
}
std::string relocation_name(std::uint32_t t) {
    static const std::map<std::uint32_t,std::string> names={{0,"R_X86_64_NONE"},{1,"R_X86_64_64"},{2,"R_X86_64_PC32"},{4,"R_X86_64_PLT32"},{5,"R_X86_64_COPY"},{6,"R_X86_64_GLOB_DAT"},{7,"R_X86_64_JUMP_SLOT"},{8,"R_X86_64_RELATIVE"},{9,"R_X86_64_GOTPCREL"},{10,"R_X86_64_32"},{11,"R_X86_64_32S"},{16,"R_X86_64_DTPMOD64"},{17,"R_X86_64_DTPOFF64"},{18,"R_X86_64_TPOFF64"},{41,"R_X86_64_GOTPCRELX"},{42,"R_X86_64_REX_GOTPCRELX"}};
    auto it=names.find(t);return it==names.end()?"R_X86_64_UNKNOWN_"+std::to_string(t):it->second;
}
std::string json(const File& f) {
    const auto& h=f.header;std::ostringstream o;
    o<<"{\"path\":"<<quote(f.path)<<",\"file_bytes\":"<<f.bytes<<",\"header\":{\"class\":64,\"encoding\":\"little-endian\",\"type\":"<<h.type<<",\"machine\":"<<h.machine<<",\"entry\":"<<h.entry<<",\"phoff\":"<<h.phoff<<",\"shoff\":"<<h.shoff<<",\"flags\":"<<h.flags<<",\"ehsize\":"<<h.ehsize<<",\"phentsize\":"<<h.phentsize<<",\"phnum\":"<<h.phnum<<",\"shentsize\":"<<h.shentsize<<",\"shnum\":"<<h.shnum<<",\"shstrndx\":"<<h.shstrndx<<"},\"sections\":[";
    for(std::size_t n=0;n<f.sections.size();++n) {if(n)o<<',';const auto& s=f.sections[n];o<<"{\"index\":"<<n<<",\"name\":"<<quote(s.name)<<",\"type\":"<<s.type<<",\"flags\":"<<s.flags<<",\"address\":"<<s.address<<",\"offset\":"<<s.offset<<",\"size\":"<<s.size<<",\"link\":"<<s.link<<",\"info\":"<<s.info<<",\"alignment\":"<<s.alignment<<",\"entry_size\":"<<s.entry_size<<'}';}
    o<<"],\"symbols\":[";
    for(std::size_t n=0;n<f.symbols.size();++n) {if(n)o<<',';const auto& s=f.symbols[n];o<<"{\"table\":"<<s.table<<",\"index\":"<<s.index<<",\"name\":"<<quote(s.name)<<",\"value\":"<<s.value<<",\"size\":"<<s.size<<",\"binding\":"<<static_cast<unsigned>(s.binding)<<",\"type\":"<<static_cast<unsigned>(s.type)<<",\"visibility\":"<<static_cast<unsigned>(s.visibility)<<",\"section\":"<<s.section<<",\"defined\":"<<(s.section?"true":"false")<<'}';}
    o<<"],\"relocations\":[";
    for(std::size_t n=0;n<f.relocations.size();++n) {if(n)o<<',';const auto& r=f.relocations[n];o<<"{\"section\":"<<r.section<<",\"target_section\":"<<r.target<<",\"symbol_table\":"<<r.symbol_table<<",\"symbol_index\":"<<r.symbol_index<<",\"offset\":"<<r.offset<<",\"type\":"<<r.type<<",\"type_name\":"<<quote(relocation_name(r.type))<<",\"symbol\":"<<quote(r.symbol)<<",\"addend\":";if(r.has_addend)o<<r.addend;else o<<"null";o<<'}';}
    o<<"]}";return o.str();
}
LinkReport link_check(const std::vector<File>& files) {
    struct Definition {std::size_t file;const Symbol* symbol;};
    std::map<std::string,std::vector<Definition>> definitions,references;
    for(std::size_t n=0;n<files.size();++n) {
        if(files[n].header.type!=1) throw std::runtime_error("link-check requires relocatable objects");
        for(const auto& s:files[n].symbols) {
            if(s.binding==0 || s.name.empty()) continue;
            if(s.binding!=1 && s.binding!=2) throw std::runtime_error("unsupported symbol binding in link-check");
            (s.section?definitions:references)[s.name].push_back({n,&s});
        }
    }
    std::ostringstream o;o<<"{\"model\":\"supplied relocatable objects; no implicit libraries\",\"definitions\":[";bool first=true;bool errors=false;
    for(const auto& [name,defs]:definitions) {
        if(!first) { o<<','; }
        first=false;
        std::size_t strong=0; const Definition* winner=&defs[0];int rank=-1;
        for(const auto& d:defs) {
            const auto& s=*d.symbol;int current=s.binding==2?0:(s.section==65522?1:2);
            if(current==2)++strong;
            if(current>rank || (current==1 && rank==1 && s.size>winner->symbol->size)) {rank=current;winner=&d;}
        }
        const bool duplicate=strong>1;errors=errors||duplicate;
        o<<"{\"name\":"<<quote(name)<<",\"candidate_count\":"<<defs.size()<<",\"strong_definitions\":"<<strong<<",\"duplicate_strong\":"<<(duplicate?"true":"false")<<",\"selected_file\":"<<quote(files[winner->file].path)<<",\"selected_kind\":"<<quote(rank==2?"strong":rank==1?"common":"weak")<<'}';
    }
    o<<"],\"references\":[";first=true;
    for(const auto& [name,refs]:references) for(const auto& ref:refs) {
        if(!first) { o<<','; }
        first=false;
        bool resolved=definitions.count(name)!=0,weak=ref.symbol->binding==2;
        const bool synthesized=!resolved && name=="_GLOBAL_OFFSET_TABLE_";
        errors=errors||(!resolved&&!weak&&!synthesized);
        o<<"{\"name\":"<<quote(name)<<",\"file\":"<<quote(files[ref.file].path)<<",\"weak\":"<<(weak?"true":"false")<<",\"resolution\":"<<quote(resolved?"resolved":synthesized?"linker_synthesized_got":weak?"optional_undefined_weak":"unresolved_in_supplied_objects")<<",\"relocations\":[";
        bool first_rel=true;
        for(const auto& rel:files[ref.file].relocations) if(rel.symbol_table==ref.symbol->table && rel.symbol_index==ref.symbol->index) {
            if(!first_rel) { o<<','; }
            first_rel=false;o<<"{\"relocation_section\":"<<rel.section<<",\"target_section\":"<<rel.target<<",\"offset\":"<<rel.offset<<",\"type\":"<<quote(relocation_name(rel.type))<<'}';
        }o<<"]}";
    }
    o<<"],\"has_errors\":"<<(errors?"true":"false")<<'}';return {o.str(),errors};
}
}
