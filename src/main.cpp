#include "elfscope.hpp"
#include <algorithm>
#include <chrono>
#include <iostream>
#include <stdexcept>
int main(int argc,char** argv) {
    try {
        if(argc<3) throw std::runtime_error("usage: elfscope inspect|sections|symbols|relocations file [--json]; elfscope link-check files...");
        const std::string command=argv[1];
        if(command=="link-check") {
            std::vector<elfscope::File> files;for(int n=2;n<argc;++n)files.push_back(elfscope::parse(argv[n]));
            auto result=elfscope::link_check(files);std::cout<<result.json<<'\n';return result.has_errors?2:0;
        }
        if(argc>4 || (argc==4 && std::string(argv[3])!="--json")) throw std::runtime_error("unexpected argument");
        auto f=elfscope::parse(argv[2]);
        if(command=="benchmark") {
            std::vector<double> samples; std::size_t observed=0;
            for(int s=0;s<15;++s) {
                auto start=std::chrono::steady_clock::now();
                for(int n=0;n<20;++n) { auto parsed=elfscope::parse(argv[2]);observed+=parsed.symbols.size()+parsed.sections.size()+parsed.relocations.size(); }
                samples.push_back(std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-start).count()/20.0);
            }
            std::sort(samples.begin(),samples.end());
            std::cout<<"{\"file_bytes\":"<<f.bytes<<",\"samples\":15,\"batch_size\":20,\"latency_us_median\":"<<samples[7]<<",\"latency_us_min\":"<<samples.front()<<",\"latency_us_max\":"<<samples.back()<<",\"throughput_MB_s\":"<<(static_cast<double>(f.bytes)/samples[7])<<",\"observed_records\":"<<observed<<",\"latency_us_samples\":[";
            for(std::size_t n=0;n<samples.size();++n) { if(n) std::cout<<',';std::cout<<samples[n]; }std::cout<<"]}\n";return 0;
        }
        if(command!="inspect" && command!="sections" && command!="symbols" && command!="relocations") throw std::runtime_error("unknown command");
        if(argc==4) {std::cout<<elfscope::json(f)<<'\n';return 0;}
        if(command=="inspect") {
            std::cout<<"ELF64 little-endian x86-64 type="<<f.header.type<<" bytes="<<f.bytes<<"\nsections="<<f.sections.size()<<" symbols="<<f.symbols.size()<<" relocations="<<f.relocations.size()<<'\n';
        } else if(command=="sections") {
            std::cout<<"INDEX NAME TYPE OFFSET SIZE LINK INFO\n";
            for(std::size_t n=0;n<f.sections.size();++n) {const auto& s=f.sections[n];std::cout<<n<<' '<<elfscope::quote(s.name)<<' '<<s.type<<' '<<s.offset<<' '<<s.size<<' '<<s.link<<' '<<s.info<<'\n';}
        } else if(command=="symbols") {
            std::cout<<"TABLE:INDEX NAME BIND TYPE SECTION VALUE SIZE\n";
            for(const auto& s:f.symbols)std::cout<<s.table<<':'<<s.index<<' '<<elfscope::quote(s.name)<<' '<<static_cast<unsigned>(s.binding)<<' '<<static_cast<unsigned>(s.type)<<' '<<s.section<<' '<<s.value<<' '<<s.size<<'\n';
        } else {
            std::cout<<"RELOCATION_SECTION TARGET OFFSET TYPE SYMBOL ADDEND\n";
            for(const auto& r:f.relocations) { std::cout<<r.section<<' '<<r.target<<' '<<r.offset<<' '<<elfscope::relocation_name(r.type)<<' '<<elfscope::quote(r.symbol)<<' ';if(r.has_addend)std::cout<<r.addend;else std::cout<<"implicit";std::cout<<'\n'; }
        }
        return 0;
    } catch(const std::exception& e) {std::cerr<<"elfscope: "<<e.what()<<'\n';return 1;}
}
