#pragma once
#include <cstdint>

// P2 mode-entry memory treatments (MC_RAPTOR_RINI). Only the GRU hidden state and previous action are
// written; RAPTOR's activation target capture is untouched. Mode 0 is the original reset, mode 1 the
// pre-existing "preserve shadow memory" path (kept in mc_raptor.cpp verbatim).
namespace handover_research {
constexpr unsigned GRU_DIM=16, ACTION_DIM=4, MEMORY_DIM=GRU_DIM+ACTION_DIM;
enum EntryMode : int32_t {
    ENTRY_RESET=0,           // N0
    ENTRY_PRESERVE_SHADOW=1, // N2s
    ENTRY_CLASSIC_ACTION=2,  // N1: GRU zero, previous action = classic's last applied motors
    ENTRY_TEACHER_GRU=3,     // N2g: teacher-forced shadow GRU kept, previous action reset
    ENTRY_TEACHER_FULL=4,    // N2: teacher-forced shadow GRU kept, previous action = classic's last applied motors
    ENTRY_STAGED=5,          // N*: staged GRU and previous action
    ENTRY_MODE_MAX=5};
enum EntryResult : uint8_t {ENTRY_NONE=0,ENTRY_APPLIED=1,ENTRY_NO_CLASSIC_ACTION=2,ENTRY_NO_STAGED=3,ENTRY_UNKNOWN_MODE=4};
// While RAPTOR is inactive, its shadow inference sees classic's applied motors as previous action.
inline bool teacher_forcing(int32_t mode) {return mode==ENTRY_TEACHER_GRU || mode==ENTRY_TEACHER_FULL;}
inline bool needs_classic_action(int32_t mode) {return mode==ENTRY_CLASSIC_ACTION || mode==ENTRY_TEACHER_FULL;}
// Memory after the original reset for modes 2..5. `before` is the memory just before reset, `reset_action`
// the original reset value of the previous action. `out` is written only on ENTRY_APPLIED.
inline EntryResult entry_memory(int32_t mode,const float *before,const float *classic,bool classic_valid,
                                const float *staged,unsigned staged_dim,float reset_action,float *out) {
    if(mode<ENTRY_CLASSIC_ACTION || mode>ENTRY_MODE_MAX)return ENTRY_UNKNOWN_MODE;
    if(needs_classic_action(mode) && !classic_valid)return ENTRY_NO_CLASSIC_ACTION;
    if(mode==ENTRY_STAGED && staged_dim!=MEMORY_DIM)return ENTRY_NO_STAGED;
    float memory[MEMORY_DIM]{};
    for(unsigned i=0;i<ACTION_DIM;i++)memory[GRU_DIM+i]=reset_action;
    if(mode==ENTRY_TEACHER_GRU || mode==ENTRY_TEACHER_FULL)for(unsigned i=0;i<GRU_DIM;i++)memory[i]=before[i];
    if(needs_classic_action(mode))for(unsigned i=0;i<ACTION_DIM;i++)memory[GRU_DIM+i]=classic[i];
    if(mode==ENTRY_STAGED)for(unsigned i=0;i<MEMORY_DIM;i++)memory[i]=staged[i];
    for(unsigned i=0;i<MEMORY_DIM;i++)out[i]=memory[i];
    return ENTRY_APPLIED;
}
}
