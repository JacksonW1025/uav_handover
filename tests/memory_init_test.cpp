#include "../research/state/MemoryInit.hpp"
#include "../research/state/StateOps.hpp"
#include <cassert>
#include <initializer_list>
#include <limits>
using namespace handover_research;
int main() {
 float before[MEMORY_DIM],classic[ACTION_DIM]={.31f,.32f,.33f,.34f},staged[MEMORY_DIM],exitm[MEMORY_DIM],out[MEMORY_DIM];
 for(unsigned i=0;i<MEMORY_DIM;i++){before[i]=.01f*(i+1);staged[i]=-.02f*(i+1);exitm[i]=.03f*(i+1)-.3f;}
 const float reset=0.f;
 auto fill=[&](){for(unsigned i=0;i<MEMORY_DIM;i++)out[i]=99.f;};
 // N1: GRU zero, previous action = classic.
 fill();assert(entry_memory(ENTRY_CLASSIC_ACTION,before,classic,true,staged,MEMORY_DIM,exitm,false,reset,out)==ENTRY_APPLIED);
 for(unsigned i=0;i<GRU_DIM;i++)assert(out[i]==0.f);
 for(unsigned i=0;i<ACTION_DIM;i++)assert(out[GRU_DIM+i]==classic[i]);
 // N2g: teacher-forced GRU kept, previous action reset; no classic command needed.
 fill();assert(entry_memory(ENTRY_TEACHER_GRU,before,classic,false,staged,0,exitm,false,reset,out)==ENTRY_APPLIED);
 for(unsigned i=0;i<GRU_DIM;i++)assert(out[i]==before[i]);
 for(unsigned i=0;i<ACTION_DIM;i++)assert(out[GRU_DIM+i]==reset);
 // N2: GRU kept and classic previous action.
 fill();assert(entry_memory(ENTRY_TEACHER_FULL,before,classic,true,staged,0,exitm,false,reset,out)==ENTRY_APPLIED);
 for(unsigned i=0;i<GRU_DIM;i++)assert(out[i]==before[i]);
 for(unsigned i=0;i<ACTION_DIM;i++)assert(out[GRU_DIM+i]==classic[i]);
 // N*: staged memory only when exactly 20 values were staged.
 fill();assert(entry_memory(ENTRY_STAGED,before,classic,false,staged,MEMORY_DIM,exitm,false,reset,out)==ENTRY_APPLIED);
 for(unsigned i=0;i<MEMORY_DIM;i++)assert(out[i]==staged[i]);
 fill();assert(entry_memory(ENTRY_STAGED,before,classic,true,staged,19,exitm,false,reset,out)==ENTRY_NO_STAGED && out[0]==99.f);
 // N3 (P3): the memory held at the most recent exit, exactly; nothing is written without one.
 fill();assert(entry_memory(ENTRY_EXIT_MEMORY,before,classic,false,staged,0,exitm,true,reset,out)==ENTRY_APPLIED);
 for(unsigned i=0;i<MEMORY_DIM;i++)assert(out[i]==exitm[i]);
 fill();assert(entry_memory(ENTRY_EXIT_MEMORY,before,classic,true,staged,MEMORY_DIM,exitm,false,reset,out)==ENTRY_NO_EXIT_MEMORY && out[0]==99.f);
 // Modes 2..5 ignore the exit memory.
 fill();assert(entry_memory(ENTRY_TEACHER_FULL,before,classic,true,staged,0,exitm,true,reset,out)==ENTRY_APPLIED && out[0]==before[0] && out[GRU_DIM]==classic[0]);
 // Missing classic command or a mode outside 2..6 writes nothing.
 fill();assert(entry_memory(ENTRY_CLASSIC_ACTION,before,classic,false,staged,MEMORY_DIM,exitm,true,reset,out)==ENTRY_NO_CLASSIC_ACTION && out[0]==99.f);
 fill();assert(entry_memory(ENTRY_TEACHER_FULL,before,classic,false,staged,MEMORY_DIM,exitm,true,reset,out)==ENTRY_NO_CLASSIC_ACTION && out[19]==99.f);
 for(int mode:{-1,0,1,7})
  {fill();assert(entry_memory(mode,before,classic,true,staged,MEMORY_DIM,exitm,true,reset,out)==ENTRY_UNKNOWN_MODE && out[0]==99.f);}
 assert(!teacher_forcing(ENTRY_EXIT_MEMORY) && !needs_classic_action(ENTRY_EXIT_MEMORY));
 // Exit memory lifecycle: nothing before the first activation; stored once on the first inactive cycle after an
 // active one; unchanged while inactive (the live shadow memory keeps evolving) and while active again.
 ExitMemory e;float live[MEMORY_DIM];
 for(unsigned i=0;i<MEMORY_DIM;i++)live[i]=.1f;
 assert(!e.due(false) && !e.valid);
 assert(!e.due(true) && !e.due(true));
 assert(e.due(false));e.store(live);assert(e.valid && e.memory[5]==.1f);
 for(unsigned i=0;i<MEMORY_DIM;i++)live[i]=.7f;
 assert(!e.due(false) && !e.due(false) && e.memory[5]==.1f);
 assert(!e.due(true) && e.memory[19]==.1f && e.valid);
 assert(e.due(false));e.store(live);assert(e.memory[5]==.7f && !e.due(false));
 // Teacher forcing only in N2g/N2; classic command needed by N1/N2 at entry.
 assert(!teacher_forcing(ENTRY_RESET) && !teacher_forcing(ENTRY_PRESERVE_SHADOW) && !teacher_forcing(ENTRY_CLASSIC_ACTION));
 assert(teacher_forcing(ENTRY_TEACHER_GRU) && teacher_forcing(ENTRY_TEACHER_FULL) && !teacher_forcing(ENTRY_STAGED));
 assert(needs_classic_action(ENTRY_CLASSIC_ACTION) && needs_classic_action(ENTRY_TEACHER_FULL) && !needs_classic_action(ENTRY_TEACHER_GRU));
 // STAGE stores validated values without touching the live state, in any activity state.
 StateOps s;float v[26]{},bounds[26],zero[26]{},input[26]{};
 for(unsigned i=0;i<26;i++){bounds[i]=1.f;v[i]=.5f;}
 for(unsigned i=0;i<20;i++)input[i]=-.1f*(i%10);
 assert(s.process(STAGE,true,v,26,bounds,zero,input,20)==SUCCESS && s.staged_dim==20 && s.staged[9]==input[9] && v[9]==.5f);
 assert(s.process(STAGE,false,v,26,bounds,zero,input,0)==DIMENSION && s.staged_dim==20);
 assert(s.process(STAGE,false,v,26,bounds,zero,input,27)==DIMENSION);
 const float kept=input[3];input[3]=std::numeric_limits<float>::quiet_NaN();
 assert(s.process(STAGE,false,v,26,bounds,zero,input,20)==NONFINITE && s.staged[3]==kept);
 input[3]=2.f;assert(s.process(STAGE,false,v,26,bounds,zero,input,20)==BOUNDS && s.staged_dim==20 && s.staged[3]==kept);
}
