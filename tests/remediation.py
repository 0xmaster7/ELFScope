#!/usr/bin/env python3
"""E-1 linker regressions and E-2 oracle mutation tests; no patched executable."""
import copy,json,pathlib,struct,sys,tempfile
from test import command,fixtures,reference,link_cases
import test as oracle

def validate(binary):
    with tempfile.TemporaryDirectory() as temp:
        root=pathlib.Path(temp);paths=fixtures(root)
        original_checks=sum(reference(binary,p)[1] for p in paths)
        # New GNU assembler inputs have explicit source-level expectations.
        sources={
            'unused':'.globl missing\n.globl foo\n.text\nfoo: ret\n',
            'active':'.globl missing\n.data\n.quad missing\n',
            'weakref':'.weak optional\n.data\n.quad optional\n',
            'none':'.globl missing\n.data\n.reloc ., R_X86_64_NONE, missing\n.quad 0\n',
            'missing_provider':'.globl missing\n.data\nmissing: .quad 3\n',
            'xref':'.data\n.quad x\n',
            'strong':'.globl x\n.data\nx: .quad 7\n',
            'strong2':'.globl x\n.data\nx: .quad 8\n',
            'weakdef':'.weak x\n.data\nx: .quad 9\n',
            'smallcommon':'.comm x,8,8\n',
            'largecommon':'.comm x,32,8\n',
            'got':'.globl _GLOBAL_OFFSET_TABLE_\n.text\ngot_user: lea _GLOBAL_OFFSET_TABLE_(%rip),%rax\nret\n',
            'addends':'.globl external\n.data\n.quad external+9\n.quad external-17\n.byte 0\n.reloc .-1, R_X86_64_8, external\n',
        }
        for name,source in sources.items():
            p=root/(name+'.s');p.write_text(source);command(['as','--64',p,'-o',p.with_suffix('.o')])
        def link(names,expected_code):
            objs=[root/(n+'.o') for n in names]
            result=command([binary,'link-check',*objs],check=False)
            assert result.returncode==expected_code,(names,result.returncode,result.stdout,result.stderr)
            data=json.loads(result.stdout);assert data['has_errors']==(expected_code==2)
            actual=command(['ld','-shared','--no-undefined','-o',root/'linked.so',*objs],check=False)
            assert (actual.returncode==0)==(expected_code==0),(names,actual.stderr)
            return data
        unused=link(['unused'],0);r=next(x for x in unused['references'] if x['name']=='missing')
        assert not r['active'] and not r['requires_definition'] and r['resolution']=='unused_undefined_declaration' and r['relocations']==[]
        symbols=json.loads(command([binary,'inspect',root/'unused.o','--json']).stdout)['symbols']
        assert any(s['name']=='missing' and not s['defined'] for s in symbols)
        active=link(['active'],2)['references'][0]
        assert active['active'] and active['requires_definition'] and active['resolution']=='unresolved_in_supplied_objects'
        weak=link(['weakref'],0)['references'][0]
        assert weak['active'] and not weak['requires_definition'] and weak['resolution']=='optional_undefined_weak'
        none=link(['none'],2)['references'][0];assert none['active'] and none['requires_definition']
        resolved=link(['active','missing_provider'],0)['references'][0]
        assert resolved['active'] and resolved['resolution']=='resolved'
        for names,winner,kind in [(['xref','weakdef','smallcommon','strong'],'strong','strong'),
                                  (['xref','weakdef','smallcommon'],'smallcommon','common'),
                                  (['xref','smallcommon','largecommon'],'largecommon','common'),
                                  (['xref','weakdef'],'weakdef','weak')]:
            d=link(names,0)['definitions'][0]
            assert d['selected_kind']==kind and pathlib.Path(d['selected_file']).stem==winner,(names,d)
        link(['strong','strong2'],2)
        got=link(['got'],0)['references'][0]
        assert got['name']=='_GLOBAL_OFFSET_TABLE_' and got['active'] and not got['requires_definition'] and got['resolution']=='linker_synthesized_got'
        assert link_cases(binary,root)==7
        # Unchanged corpus plus a signed-addend/unknown-type specimen and REL case.
        target=root/'addends.o';clean=json.loads(command([binary,'inspect',target,'--json']).stdout)
        reference(binary,target);reference(binary,root/'structural_rel.o')
        # Expectations come from the assembly above, not the executable's values.
        assert [r['addend'] for r in clean['relocations']]==[9,-17,0]
        real_command=oracle.command
        def reject(name,mutator,path=target):
            def injected(args,check=True):
                result=real_command(args,check)
                if len(args)>1 and args[1]=='inspect':
                    data=json.loads(result.stdout);mutator(data);result.stdout=json.dumps(data)
                return result
            oracle.command=injected
            try:
                try:reference(binary,path)
                except (AssertionError,KeyError,TypeError,ValueError,IndexError):pass
                else:raise RuntimeError('oracle accepted corrupted JSON: '+name)
            finally:oracle.command=real_command
        mutations={
            'all_null':lambda d:[r.update(addend=None) for r in d['relocations']],
            'positive_addend':lambda d:d['relocations'][0].update(addend=10),
            'negative_addend':lambda d:d['relocations'][1].update(addend=-16),
            'missing_addend':lambda d:d['relocations'][0].pop('addend'),
            'string_addend':lambda d:d['relocations'][0].update(addend='9'),
            'bool_addend':lambda d:d['relocations'][0].update(addend=True),
            'float_addend':lambda d:d['relocations'][0].update(addend=9.0),
            'relocation_type':lambda d:d['relocations'][0].update(type=2),
            'symbol_index':lambda d:d['relocations'][0].update(symbol_index=0),
            'target_section':lambda d:d['relocations'][0].update(target_section=0),
            'symbol_table':lambda d:d['relocations'][0].update(symbol_table=0),
            'missing_relationship':lambda d:d['relocations'][0].pop('target_section'),
            'known_name_as_unknown':lambda d:d['relocations'][0].update(type_name='R_X86_64_UNKNOWN_1'),
            'incorrect_unknown_name':lambda d:d['relocations'][2].update(type_name='R_X86_64_UNKNOWN_999'),
        }
        for name,mutator in mutations.items():reject(name,mutator)
        reject('REL_explicit_addend',lambda d:d['relocations'][0].update(addend=0),root/'structural_rel.o')
        return {'original_corpus_files':len(paths),'original_corpus_field_comparisons':original_checks,
                'new_link_scenarios':11,'existing_link_scenarios':7,'oracle_mutations_rejected':len(mutations)+1,'failures':0}

if __name__=='__main__':print(json.dumps(validate(str(pathlib.Path(sys.argv[1]).resolve())),indent=2))
