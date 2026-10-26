#include "research/state/P12Controls.hpp"
#include <cassert>
int main() {
 using handover_research::p12_delivery_allowed;
 // Source explicitly allows initialization, even on a committing call.
 assert(p12_delivery_allowed(2,true,false,0,2));
 assert(p12_delivery_allowed(2,true,true,0,0));
 // Once initialized at force-sync2, actual phases are distinct.
 assert(!p12_delivery_allowed(2,true,true,0,2));
 assert(p12_delivery_allowed(2,true,true,1,2));
 assert(p12_delivery_allowed(1,true,true,0,2));
 assert(!p12_delivery_allowed(1,true,true,1,2));
}
