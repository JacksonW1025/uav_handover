#pragma once
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

uint64_t usecTimestamp(void);
uint32_t simGetTickMs(void);
void watchdogReset(void);
float pmGetBatteryVoltage(void);

#ifdef __cplusplus
}
#endif
