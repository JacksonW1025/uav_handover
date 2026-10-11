#include "../research/state/SampleClock.hpp"
#include <cassert>
int main() {
    handover_research::SampleClock clock;
    // Distinct sensor observations can arrive at the same simulator wall tick.
    // Both must advance control; processing-clock deduplication would lose one.
    assert(clock.accept(50292000)==0);
    assert(clock.accept(50296000)==0 && clock.dt==4000);
    auto commits=clock.accepted;
    assert(clock.accept(50296000)==1 && clock.accepted==commits);
    assert(clock.accept(50292000)==2 && clock.accepted==commits);
    assert(clock.accept(50300000)==0 && clock.dt==4000);
    assert(clock.accept(50308000)==0 && clock.dt==8000);
    assert(clock.accept(0)==2 && clock.last==50308000);
    assert(clock.accepted==4 && clock.duplicate==1 && clock.regressed==2);
}
