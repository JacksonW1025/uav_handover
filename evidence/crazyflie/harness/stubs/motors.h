#pragma once
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

#define NBR_OF_MOTORS 4
#define MOTOR_M1  0
#define MOTOR_M2  1
#define MOTOR_M3  2
#define MOTOR_M4  3

void motorsSetRatio(uint32_t id, uint16_t ithrust);
uint16_t motorsGetRatio(uint32_t id);
float motorsCompensateBatteryVoltage(uint32_t id, float iThrust, float supplyVoltage);

#ifdef __cplusplus
}
#endif
