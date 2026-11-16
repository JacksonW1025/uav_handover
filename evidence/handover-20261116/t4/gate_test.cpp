#include <initializer_list>
#include "ActuatorGate.hpp"
#include <cassert>
#include <cstdio>
int main(){
  unsigned tests=0;
  for(bool available:{false,true})for(bool valid:{false,true})for(bool allocation:{false,true})for(bool neural:{false,true}){
    test_available=available;test_mode={valid?1u:0u,allocation};
    handover_research::ActuatorGate gate(neural);
    assert(gate.allowed()==(available&&valid&&(neural!=allocation)));++tests;
  }
  // Explicit cached-condition scenario; this schedule is a model, not a flight.
  // Neural has observed allocation=false; classic still has allocation=true.
  test_available=true;test_mode={1,false};
  bool stale_classic=true, current_neural=true;
  assert(stale_classic&&current_neural);
  bool fixed_classic,fixed_neural;
  {handover_research::ActuatorGate g(false);fixed_classic=g.allowed();}
  {handover_research::ActuatorGate g(true);fixed_neural=g.allowed();}
  assert(!fixed_classic&&fixed_neural);
  std::printf("{\"truth_table_cases\":%u,\"cached_model_allows_both\":true,\"shared_latest_allows_classic\":false,\"shared_latest_allows_neural\":true}\n",tests);
}
