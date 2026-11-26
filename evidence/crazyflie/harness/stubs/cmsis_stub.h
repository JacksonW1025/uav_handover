#pragma once
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include "stabilizer_types.h"

typedef struct {
  volatile uint32_t CYCCNT;
} SimDWT_t;

extern SimDWT_t g_sim_dwt;
#define DWT (&g_sim_dwt)

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

void controllerMellingerFirmwareInit(void);
bool controllerMellingerFirmwareTest(void);
void controllerMellingerFirmware(control_t *control, const setpoint_t *setpoint,
                                 const sensorData_t *sensors, const state_t *state,
                                 const stabilizerStep_t stabilizerStep);
