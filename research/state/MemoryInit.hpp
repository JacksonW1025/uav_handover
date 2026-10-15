#pragma once
#include <cstdint>

// P2/P3 mode-entry memory treatments (MC_RAPTOR_RINI). Only the GRU hidden state and previous action are
// written; RAPTOR's activation target capture is untouched. Mode 0 is the original reset, mode 1 the
// pre-existing "preserve shadow memory" path (kept in mc_raptor.cpp verbatim). Mode 6 (P3) restores the
// memory RAPTOR held when it last stopped owning the actuators.
namespace handover_research {
constexpr unsigned GRU_DIM=16, ACTION_DIM=4, MEMORY_DIM=GRU_DIM+ACTION_DIM;
enum EntryMode : int32_t {
    ENTRY_RESET=0,           // N0
    ENTRY_PRESERVE_SHADOW=1, // N2s
    ENTRY_CLASSIC_ACTION=2,  // N1: GRU zero, previous action = classic's last applied motors
    ENTRY_TEACHER_GRU=3,     // N2g: teacher-forced shadow GRU kept, previous action reset
    ENTRY_TEACHER_FULL=4,    // N2: teacher-forced shadow GRU kept, previous action = classic's last applied motors
    ENTRY_STAGED=5,          // N*: staged GRU and previous action
    ENTRY_EXIT_MEMORY=6,     // N3: GRU and previous action held unchanged since RAPTOR's most recent exit
    ENTRY_MODE_MAX=6};
enum EntryResult : uint8_t {ENTRY_NONE=0,ENTRY_APPLIED=1,ENTRY_NO_CLASSIC_ACTION=2,ENTRY_NO_STAGED=3,ENTRY_UNKNOWN_MODE=4,ENTRY_NO_EXIT_MEMORY=5};
// While RAPTOR is inactive, its shadow inference sees classic's applied motors as previous action.
inline bool teacher_forcing(int32_t mode) {return mode==ENTRY_TEACHER_GRU || mode==ENTRY_TEACHER_FULL;}
inline bool needs_classic_action(int32_t mode) {return mode==ENTRY_CLASSIC_ACTION || mode==ENTRY_TEACHER_FULL;}
// Memory after the original reset for modes 2..6. `before` is the memory just before reset, `exit_memory` the
// memory held at the most recent exit, `reset_action` the original reset value of the previous action.
// `out` is written only on ENTRY_APPLIED.
inline EntryResult entry_memory(int32_t mode,const float *before,const float *classic,bool classic_valid,
                                const float *staged,unsigned staged_dim,const float *exit_memory,bool exit_valid,
                                float reset_action,float *out) {
    if(mode<ENTRY_CLASSIC_ACTION || mode>ENTRY_MODE_MAX)return ENTRY_UNKNOWN_MODE;
    if(needs_classic_action(mode) && !classic_valid)return ENTRY_NO_CLASSIC_ACTION;
    if(mode==ENTRY_STAGED && staged_dim!=MEMORY_DIM)return ENTRY_NO_STAGED;
    if(mode==ENTRY_EXIT_MEMORY && !exit_valid)return ENTRY_NO_EXIT_MEMORY;
    float memory[MEMORY_DIM]{};
    for(unsigned i=0;i<ACTION_DIM;i++)memory[GRU_DIM+i]=reset_action;
    if(mode==ENTRY_TEACHER_GRU || mode==ENTRY_TEACHER_FULL)for(unsigned i=0;i<GRU_DIM;i++)memory[i]=before[i];
    if(needs_classic_action(mode))for(unsigned i=0;i<ACTION_DIM;i++)memory[GRU_DIM+i]=classic[i];
    if(mode==ENTRY_STAGED)for(unsigned i=0;i<MEMORY_DIM;i++)memory[i]=staged[i];
    if(mode==ENTRY_EXIT_MEMORY)for(unsigned i=0;i<MEMORY_DIM;i++)memory[i]=exit_memory[i];
    for(unsigned i=0;i<MEMORY_DIM;i++)out[i]=memory[i];
    return ENTRY_APPLIED;
}
// P3: memory RAPTOR held when it last stopped being active. The controller calls due() once per cycle, before that
// cycle's mode-entry write or inference; on the first inactive cycle after an active one it stores the live memory
// (committed GRU and previous action of the last active inference). The stored copy stays unchanged until the next exit.
struct ExitMemory {
    float memory[MEMORY_DIM]{};
    bool valid{false},armed{false};
    bool due(bool active) {if(active){armed=true;return false;}return armed;}
    void store(const float *live) {for(unsigned i=0;i<MEMORY_DIM;i++)memory[i]=live[i];valid=true;armed=false;}
};
}
