#include "../research/state/P12Controls.hpp"
#include <cassert>
int main() {
    using namespace handover_research;
    for (uint64_t k=0;k<1000;k++) {
        assert(p12_delivery_allowed(1,true,true,k,2)==(k%2==0));
        assert(p12_delivery_allowed(2,true,true,k,2)==(k%2==1));
        assert(p12_delivery_allowed(0,true,true,k,2));
        assert(p12_delivery_allowed(1,false,true,k,2));
        assert(p12_capture_mode(true,true,true,true)==0);
        assert(p12_capture_mode(true,false,true,false)==0);
        assert(p12_capture_mode(false,false,true,true)==0);
        assert(p12_capture_mode(true,false,true,true)==2);
    }
}
