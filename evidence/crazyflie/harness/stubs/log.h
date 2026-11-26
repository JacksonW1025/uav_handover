#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define LOG_UINT8  1
#define LOG_UINT16 2
#define LOG_UINT32 3
#define LOG_INT8   4
#define LOG_INT16  5
#define LOG_INT32  6
#define LOG_FLOAT  7
#define LOG_FP16   8

#define LOG_CORE 0x20
#define LOG_BY_FUNCTION 0x40
#define LOG_GROUP 0x80
#define LOG_START 1
#define LOG_STOP  0

struct log_s {
  uint8_t type;
  const char *name;
  void *address;
};

void sim_register_log_group_terminated(const struct log_s *group);

#define LOG_ADD(TYPE, NAME, ADDRESS) \
  { .type = (uint8_t)(TYPE), .name = #NAME, .address = (void*)(ADDRESS) },

#define LOG_ADD_CORE(TYPE, NAME, ADDRESS) LOG_ADD((TYPE) | LOG_CORE, NAME, ADDRESS)
#define LOG_ADD_BY_FUNCTION(TYPE, NAME, ADDRESS) LOG_ADD((TYPE) | LOG_BY_FUNCTION, NAME, ADDRESS)
#define LOG_ADD_GROUP(TYPE, NAME, ADDRESS) \
  { .type = (uint8_t)(TYPE), .name = #NAME, .address = (void*)(ADDRESS) },

#define LOG_GROUP_START(NAME) \
  static const struct log_s __logs_##NAME[]; \
  __attribute__((constructor)) static void __sim_reg_log_##NAME(void) { \
    sim_register_log_group_terminated(__logs_##NAME); \
  } \
  static const struct log_s __logs_##NAME[] = { \
  LOG_ADD_GROUP(LOG_GROUP | LOG_START, NAME, 0x0)

#define LOG_GROUP_STOP(NAME) \
  LOG_ADD_GROUP(LOG_GROUP | LOG_STOP, stop_##NAME, 0x0) \
  };

#ifdef __cplusplus
}
#endif
