#pragma once
// Scheduler-only harness: the component barrier is outside this test's scope.
#include <semaphore.h>
#include <unistd.h>
using px4_sem_t = sem_t;
inline void system_usleep(unsigned usec) { usleep(usec); }
