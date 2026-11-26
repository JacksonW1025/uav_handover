#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define PARAM_BYTES_MASK 0x03
#define PARAM_1BYTE  0x00
#define PARAM_2BYTES 0x01
#define PARAM_4BYTES 0x02
#define PARAM_8BYTES 0x03
#define PARAM_TYPE_INT   (0x00<<2)
#define PARAM_TYPE_FLOAT (0x01<<2)
#define PARAM_SIGNED   (0x00<<3)
#define PARAM_UNSIGNED (0x01<<3)
#define PARAM_VARIABLE (0x00<<7)
#define PARAM_GROUP    (0x01<<7)
#define PARAM_START 1
#define PARAM_STOP  0
#define PARAM_SYNC 0x02
#define PARAM_RONLY (1<<6)
#define PARAM_CORE (1<<5)
#define PARAM_PERSISTENT (1 << 8)

#define PARAM_UINT8 (PARAM_1BYTE | PARAM_TYPE_INT | PARAM_UNSIGNED)
#define PARAM_INT8  (PARAM_1BYTE | PARAM_TYPE_INT | PARAM_SIGNED)
#define PARAM_UINT16 (PARAM_2BYTES | PARAM_TYPE_INT | PARAM_UNSIGNED)
#define PARAM_INT16  (PARAM_2BYTES | PARAM_TYPE_INT | PARAM_SIGNED)
#define PARAM_UINT32 (PARAM_4BYTES | PARAM_TYPE_INT | PARAM_UNSIGNED)
#define PARAM_INT32  (PARAM_4BYTES | PARAM_TYPE_INT | PARAM_SIGNED)
#define PARAM_FLOAT (PARAM_4BYTES | PARAM_TYPE_FLOAT | PARAM_SIGNED)

struct param_s {
  uint16_t type;
  const char *name;
  void *address;
  void (*callback)(void);
  const void *(*getter)(void);
};

void sim_register_param_group(const struct param_s *group, uint32_t count);

#define PARAM_ADD_FULL(TYPE, NAME, ADDRESS, CALLBACK, DEFAULT_GETTER) \
  { .type = (uint16_t)((TYPE) & 0xFFFF), .name = #NAME, .address = (void*)(ADDRESS), .callback = (void(*)(void))(CALLBACK), .getter = (const void*(*)(void))(DEFAULT_GETTER) },

#define PARAM_ADD(TYPE, NAME, ADDRESS) PARAM_ADD_FULL(TYPE, NAME, ADDRESS, 0, 0)
#define PARAM_ADD_WITH_CALLBACK(TYPE, NAME, ADDRESS, CALLBACK) PARAM_ADD_FULL(TYPE, NAME, ADDRESS, CALLBACK, 0)
#define PARAM_ADD_CORE(TYPE, NAME, ADDRESS) PARAM_ADD((TYPE) | PARAM_CORE, NAME, ADDRESS)
#define PARAM_ADD_CORE_WITH_CALLBACK(TYPE, NAME, ADDRESS, CALLBACK) PARAM_ADD_WITH_CALLBACK((TYPE) | PARAM_CORE, NAME, ADDRESS, CALLBACK)
#define PARAM_ADD_GROUP(TYPE, NAME, ADDRESS) \
  { .type = (uint16_t)(TYPE), .name = #NAME, .address = (void*)(ADDRESS), .callback = 0, .getter = 0 },

#define PARAM_GROUP_START(NAME) \
  static const struct param_s __params_##NAME[] = { \
  PARAM_ADD_GROUP(PARAM_GROUP | PARAM_START, NAME, 0x0)

#define PARAM_GROUP_STOP(NAME) \
  PARAM_ADD_GROUP(PARAM_GROUP | PARAM_STOP, stop_##NAME, 0x0) \
  }; \
  __attribute__((constructor)) static void __sim_reg_param_##NAME(void) { \
    sim_register_param_group(__params_##NAME, (uint32_t)(sizeof(__params_##NAME)/sizeof(__params_##NAME[0]))); \
  }

#ifdef __cplusplus
}
#endif
