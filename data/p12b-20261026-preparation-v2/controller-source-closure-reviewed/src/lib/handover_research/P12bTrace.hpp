#pragma once
#include <cstdint>
#include <cstdlib>
#include <fcntl.h>
#include <unistd.h>
#include <uORB/topics/research_p12b.h>
namespace handover_research {
#pragma pack(push,1)
struct P12bReadRow {
    uint32_t magic{0x42325250U}, version{2U};
    uint64_t sequence{0}, prior_write_failures{0};
    uint64_t timestamp{};
    uint64_t timestamp_sample{};
    uint64_t pre_read_wall_ns{};
    uint64_t call_index_pre{};
    uint64_t force_sync_pre{};
    uint64_t control_time_pre{};
    uint64_t original_control_time_pre{};
    uint64_t last_valid_read_pre{};
    int32_t repair_not_before_ms{};
    int32_t requested_phase{};
    uint8_t active{};
    uint8_t activation{};
    uint8_t timing_initialized_pre{};
    uint8_t force_sync_initialized_pre{};
    uint8_t gate_applicable{};
    uint8_t gate_permit{};
    uint8_t gate_pending{};
    uint8_t external_seen_pre{};
    uint8_t read_updated{};
    uint8_t read_valid{};
    uint32_t invalid_total{};
    uint64_t last_valid_read_post{};
    uint64_t external_timestamp{};
};
#pragma pack(pop)
// Passive direct evidence, never read by the controller. A write failure is
// represented by a sequence gap/counter and fails offline engineering release.
inline void p12b_trace(const research_p12b_s &m) {
    static int fd=-2;
    static uint64_t sequence=0, failures=0;
    if (fd==-2) {
        const char *path=std::getenv("HANDOVER_P12B_READ_TRACE");
        fd=path ? ::open(path,O_WRONLY|O_CREAT|O_EXCL,0664) : -1;
        if (fd<0) ++failures;
    }
    P12bReadRow row{};row.sequence=sequence++;row.prior_write_failures=failures;
    row.timestamp=m.timestamp;
    row.timestamp_sample=m.timestamp_sample;
    row.pre_read_wall_ns=m.pre_read_wall_ns;
    row.call_index_pre=m.call_index_pre;
    row.force_sync_pre=m.force_sync_pre;
    row.control_time_pre=m.control_time_pre;
    row.original_control_time_pre=m.original_control_time_pre;
    row.last_valid_read_pre=m.last_valid_read_pre;
    row.repair_not_before_ms=m.repair_not_before_ms;
    row.requested_phase=m.requested_phase;
    row.active=m.active;
    row.activation=m.activation;
    row.timing_initialized_pre=m.timing_initialized_pre;
    row.force_sync_initialized_pre=m.force_sync_initialized_pre;
    row.gate_applicable=m.gate_applicable;
    row.gate_permit=m.gate_permit;
    row.gate_pending=m.gate_pending;
    row.external_seen_pre=m.external_seen_pre;
    row.read_updated=m.read_updated;
    row.read_valid=m.read_valid;
    row.invalid_total=m.invalid_total;
    row.last_valid_read_post=m.last_valid_read_post;
    row.external_timestamp=m.external_timestamp;

    if (fd>=0 && ::write(fd,&row,sizeof(row))!=static_cast<ssize_t>(sizeof(row))) ++failures;
}
}
