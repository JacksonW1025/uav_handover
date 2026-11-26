#pragma once
#include "usec_time.h"
#define xTaskGetTickCount() simGetTickMs()
#define M2T(X) ((unsigned int)(X))
#define F2T(X) ((unsigned int)(1000/(X)))
