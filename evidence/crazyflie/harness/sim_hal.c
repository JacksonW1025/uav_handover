#include "sim_hal.h"
#include "stubs/cmsis_stub.h"
#include "stubs/param.h"
#include "stubs/log.h"
#include "motors.h"
#include <string.h>
#include <stdio.h>

SimDWT_t g_sim_dwt = {0};
static uint64_t g_sim_time_us = 0;
static float g_battery_voltage = 4.0f;

static float g_published_motor_ratios[4] = {0, 0, 0, 0};
static float g_applied_motor_ratios[4] = {0, 0, 0, 0};
static bool g_hold_motors = false;

float benchmark_data[1000] = {0};
float compute_mac_flops(void) { return 0.0f; }

void sim_set_time_us(uint64_t t_us) {
  g_sim_time_us = t_us;
  g_sim_dwt.CYCCNT = (uint32_t)(t_us * 168ULL);
}

uint64_t sim_get_time_us(void) { return g_sim_time_us; }
uint64_t usecTimestamp(void) { return g_sim_time_us; }
uint32_t simGetTickMs(void) { return (uint32_t)(g_sim_time_us / 1000ULL); }
void watchdogReset(void) {}
float pmGetBatteryVoltage(void) { return g_battery_voltage; }

void sim_reset_motors(void) {
  for (int i = 0; i < 4; i++) {
    g_published_motor_ratios[i] = 0.0f;
    g_applied_motor_ratios[i] = 0.0f;
  }
  g_hold_motors = false;
}

void sim_set_delivery_hold_Active(bool hold_current_motors) {
  g_hold_motors = hold_current_motors;
}

void motorsSetRatio(uint32_t id, uint16_t ithrust) {
  if (id < 4) {
    float r = (float)ithrust / 65535.0f;
    if (r < 0.0f) r = 0.0f;
    if (r > 1.0f) r = 1.0f;
    g_published_motor_ratios[id] = r;
    if (!g_hold_motors) {
      g_applied_motor_ratios[id] = r;
    }
  }
}

uint16_t motorsGetRatio(uint32_t id) {
  if (id < 4) return (uint16_t)(g_applied_motor_ratios[id] * 65535.0f);
  return 0;
}

float motorsCompensateBatteryVoltage(uint32_t id, float iThrust, float supplyVoltage) {
  (void)id;
  (void)supplyVoltage;
  return iThrust;
}

void sim_get_motor_ratios(float out_ratios[4]) {
  for (int i = 0; i < 4; i++) out_ratios[i] = g_applied_motor_ratios[i];
}

void sim_get_published_motor_ratios(float out_ratios[4]) {
  for (int i = 0; i < 4; i++) out_ratios[i] = g_published_motor_ratios[i];
}

typedef struct {
  char full_name[96];
  uint16_t type;
  void *address;
  void (*callback)(void);
} ParamEntry;

typedef struct {
  char full_name[96];
  uint8_t type;
  void *address;
} LogEntry;

static ParamEntry g_params[512];
static uint32_t g_num_params = 0;

static LogEntry g_logs[512];
static uint32_t g_num_logs = 0;

void sim_register_param_group(const struct param_s *group, uint32_t count) {
  const char *group_name = "global";
  for (uint32_t i = 0; i < count; i++) {
    if (group[i].type & PARAM_GROUP) {
      if (group[i].type & PARAM_START) {
        group_name = group[i].name;
      }
    } else if (group[i].address != NULL && g_num_params < 512) {
      snprintf(g_params[g_num_params].full_name, sizeof(g_params[g_num_params].full_name),
               "%s.%s", group_name, group[i].name);
      g_params[g_num_params].type = group[i].type;
      g_params[g_num_params].address = group[i].address;
      g_params[g_num_params].callback = group[i].callback;
      g_num_params++;
    }
  }
}

void sim_register_log_group_terminated(const struct log_s *group) {
  const char *group_name = "global";
  for (uint32_t i = 0; i < 256; i++) {
    if (group[i].type & LOG_GROUP) {
      if (group[i].type & LOG_START) {
        group_name = group[i].name;
      } else {
        break;
      }
    } else if (group[i].address != NULL && g_num_logs < 512) {
      snprintf(g_logs[g_num_logs].full_name, sizeof(g_logs[g_num_logs].full_name),
               "%s.%s", group_name, group[i].name);
      g_logs[g_num_logs].type = group[i].type & 0x0F;
      g_logs[g_num_logs].address = group[i].address;
      g_num_logs++;
    }
  }
}

static ParamEntry *find_param(const char *name) {
  for (uint32_t i = 0; i < g_num_params; i++) {
    if (strcmp(g_params[i].full_name, name) == 0) return &g_params[i];
  }
  return NULL;
}

static LogEntry *find_log(const char *name) {
  for (uint32_t i = 0; i < g_num_logs; i++) {
    if (strcmp(g_logs[i].full_name, name) == 0) return &g_logs[i];
  }
  return NULL;
}

bool sim_set_param_float(const char *name, float val) {
  ParamEntry *p = find_param(name);
  if (!p) return false;
  if (p->type & PARAM_TYPE_FLOAT) {
    *(float *)(p->address) = val;
  } else {
    switch (p->type & PARAM_BYTES_MASK) {
      case PARAM_1BYTE: *(uint8_t *)(p->address) = (uint8_t)val; break;
      case PARAM_2BYTES: *(uint16_t *)(p->address) = (uint16_t)val; break;
      case PARAM_4BYTES: *(int32_t *)(p->address) = (int32_t)val; break;
    }
  }
  if (p->callback) p->callback();
  return true;
}

bool sim_set_param_int(const char *name, int val) {
  ParamEntry *p = find_param(name);
  if (!p) return false;
  if (p->type & PARAM_TYPE_FLOAT) {
    *(float *)(p->address) = (float)val;
  } else {
    switch (p->type & PARAM_BYTES_MASK) {
      case PARAM_1BYTE:
        if (p->type & PARAM_UNSIGNED) *(uint8_t *)(p->address) = (uint8_t)val;
        else *(int8_t *)(p->address) = (int8_t)val;
        break;
      case PARAM_2BYTES:
        if (p->type & PARAM_UNSIGNED) *(uint16_t *)(p->address) = (uint16_t)val;
        else *(int16_t *)(p->address) = (int16_t)val;
        break;
      case PARAM_4BYTES:
        if (p->type & PARAM_UNSIGNED) *(uint32_t *)(p->address) = (uint32_t)val;
        else *(int32_t *)(p->address) = (int32_t)val;
        break;
    }
  }
  if (p->callback) p->callback();
  return true;
}

float sim_get_param_float(const char *name, bool *ok) {
  ParamEntry *p = find_param(name);
  if (!p) { if (ok) *ok = false; return 0.0f; }
  if (ok) *ok = true;
  if (p->type & PARAM_TYPE_FLOAT) return *(float *)(p->address);
  return (float)(*(uint8_t *)(p->address));
}

int sim_get_param_int(const char *name, bool *ok) {
  ParamEntry *p = find_param(name);
  if (!p) { if (ok) *ok = false; return 0; }
  if (ok) *ok = true;
  switch (p->type & PARAM_BYTES_MASK) {
    case PARAM_1BYTE: return (p->type & PARAM_UNSIGNED) ? *(uint8_t *)(p->address) : *(int8_t *)(p->address);
    case PARAM_2BYTES: return (p->type & PARAM_UNSIGNED) ? *(uint16_t *)(p->address) : *(int16_t *)(p->address);
    case PARAM_4BYTES: return *(int32_t *)(p->address);
  }
  return 0;
}

float sim_get_log_float(const char *name, bool *ok) {
  LogEntry *l = find_log(name);
  if (!l) { if (ok) *ok = false; return 0.0f; }
  if (ok) *ok = true;
  if (l->type == LOG_FLOAT) return *(float *)(l->address);
  if (l->type == LOG_UINT8) return (float)(*(uint8_t *)(l->address));
  return 0.0f;
}

int sim_get_log_int(const char *name, bool *ok) {
  LogEntry *l = find_log(name);
  if (!l) { if (ok) *ok = false; return 0; }
  if (ok) *ok = true;
  if (l->type == LOG_UINT8) return *(uint8_t *)(l->address);
  if (l->type == LOG_FLOAT) return (int)(*(float *)(l->address));
  return 0;
}
