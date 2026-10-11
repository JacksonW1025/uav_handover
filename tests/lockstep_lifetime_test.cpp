// Link with --wrap=pthread_mutex_lock to pause the actual scheduler immediately
// before it touches a selected caller-owned mutex. No production test hooks.
#include <lockstep_scheduler/lockstep_scheduler.h>
#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <thread>
#include <cerrno>
#include <vector>

LockstepComponents::LockstepComponents(bool b) : _no_cleanup_on_destroy(b) {}
LockstepComponents::~LockstepComponents() = default;

static pthread_mutex_t caller_mutex = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t caller_cond = PTHREAD_COND_INITIALIZER;
static std::atomic<bool> pause_clock{false}, clock_paused{false}, release_clock{false};
static std::atomic<bool> waiter_entered{false}, waiter_returned{false};
static thread_local bool is_clock = false;
extern "C" int __real_pthread_mutex_lock(pthread_mutex_t *);
extern "C" int __wrap_pthread_mutex_lock(pthread_mutex_t *m)
{
    if (is_clock && m == &caller_mutex && pause_clock) {
        clock_paused = true;
        while (!release_clock) std::this_thread::yield();
    }
    return __real_pthread_mutex_lock(m);
}
static bool await(const std::atomic<bool> &flag)
{
    auto until = std::chrono::steady_clock::now() + std::chrono::seconds(5);
    while (!flag) {
        if (std::chrono::steady_clock::now() > until) return false;
        std::this_thread::yield();
    }
    return true;
}
int main()
{
    LockstepScheduler scheduler;
    scheduler.set_absolute_time(1);
    int result = -1;
    std::thread waiter([&] {
        pthread_mutex_lock(&caller_mutex);
        waiter_entered = true;
        result = scheduler.cond_timedwait(&caller_cond, &caller_mutex, 2);
        waiter_returned = true; // After this point callers may destroy stack locks.
        pthread_mutex_unlock(&caller_mutex);
    });
    if (!await(waiter_entered)) std::abort();
    // Acquiring the lock proves cond_timedwait registered and released it.
    pthread_mutex_lock(&caller_mutex);
    pthread_mutex_unlock(&caller_mutex);
    pause_clock = true;
    std::thread clock([&] { is_clock = true; scheduler.set_absolute_time(2); });
    if (!await(clock_paused)) std::abort();
    // A normal external signal (or spurious wake) races the pending timeout.
    pthread_cond_broadcast(&caller_cond);
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
    const bool returned_before_clock_finished = waiter_returned;
    release_clock = true;
    clock.join();
    if (!await(waiter_returned)) std::abort();
    scheduler.set_absolute_time(3); // Retire TLS entry before thread destruction.
    waiter.join();
    std::printf("returned_before_pending_broadcast=%s result=%d\n",
                returned_before_clock_finished ? "true" : "false", result);
    if (returned_before_clock_finished || result != ETIMEDOUT) return 1;

    // More than the previous fixed 32-entry wakeup buffer: no waiter may be
    // marked timed out and then silently omitted from the broadcast list.
    constexpr int count = 64;
    std::atomic<int> ready{0}, completed{0}, errors{0};
    std::vector<std::thread> waiters;
    for (int i = 0; i < count; ++i) waiters.emplace_back([&] {
        pthread_mutex_lock(&caller_mutex);
        ++ready;
        if (scheduler.cond_timedwait(&caller_cond, &caller_mutex, 100) != ETIMEDOUT) ++errors;
        ++completed;
        pthread_mutex_unlock(&caller_mutex);
    });
    auto until = std::chrono::steady_clock::now() + std::chrono::seconds(5);
    while (ready != count && std::chrono::steady_clock::now() < until) std::this_thread::yield();
    if (ready != count) std::abort();
    pthread_mutex_lock(&caller_mutex);
    pthread_mutex_unlock(&caller_mutex);
    scheduler.set_absolute_time(100);
    until = std::chrono::steady_clock::now() + std::chrono::seconds(5);
    while (completed != count && std::chrono::steady_clock::now() < until) std::this_thread::yield();
    if (completed != count) std::abort();
    scheduler.set_absolute_time(101);
    for (auto &thread : waiters) thread.join();
    std::printf("simultaneous_timeouts=%d errors=%d\n", completed.load(), errors.load());
    return errors ? 1 : 0;
}
