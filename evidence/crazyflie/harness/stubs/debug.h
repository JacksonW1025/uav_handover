#pragma once
#include <stdio.h>
#define DEBUG_PRINT(...) do {} while(0)
#define ASSERT(e) do { if(!(e)) { fprintf(stderr, "ASSERT FAILED: %s (%s:%d)\n", #e, __FILE__, __LINE__); } } while(0)
