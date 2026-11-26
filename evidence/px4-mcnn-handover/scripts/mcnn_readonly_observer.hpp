#pragma once

#ifdef __PX4_POSIX

#include <atomic>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <mutex>

namespace mcnn_obs
{

struct Snapshot {
	int is_neural{0};
	int64_t pub_seq{0};
};

class Observer
{
public:
	static Observer &instance()
	{
		static Observer inst;
		return inst;
	}

	void record_mode_request(uint64_t t_us, uint8_t desired_nav_state)
	{
		std::lock_guard<std::mutex> lock(_mutex);
		ensure_open();

		if (_fp != nullptr) {
			std::fprintf(_fp, "mode_request,%llu,%u,0,0,0,0,0,0,0,0,0,0,0,0,0\n",
				     static_cast<unsigned long long>(t_us),
				     static_cast<unsigned>(desired_nav_state));
			std::fflush(_fp);
		}
	}

	void record_mode_transition(bool active, uint64_t t_us, int mode_id,
				    uint64_t sp_ts, const float sp_pos[3],
				    float px, float py, float pz)
	{
		if (!active) {
			_session_pub_count.store(0, std::memory_order_release);
		}

		std::lock_guard<std::mutex> lock(_mutex);
		ensure_open();

		if (_fp != nullptr) {
			std::fprintf(_fp, "%s,%llu,%d,%lld,%llu,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,0,0,0,0,0\n",
				     active ? "mcnn_active" : "mcnn_inactive",
				     static_cast<unsigned long long>(t_us),
				     mode_id,
				     static_cast<long long>(_pub_seq.load(std::memory_order_relaxed)),
				     static_cast<unsigned long long>(sp_ts),
				     static_cast<double>(sp_pos[0]),
				     static_cast<double>(sp_pos[1]),
				     static_cast<double>(sp_pos[2]),
				     static_cast<double>(px),
				     static_cast<double>(py),
				     static_cast<double>(pz));
			std::fflush(_fp);
		}
	}

	void on_neural_inactive()
	{
		_session_pub_count.store(0, std::memory_order_release);
	}

	int64_t before_neural_publish()
	{
		const int64_t seq = _pub_seq.fetch_add(1, std::memory_order_acq_rel) + 1;
		_session_pub_count.fetch_add(1, std::memory_order_release);
		return seq;
	}

	void after_neural_publish(uint64_t t_us, int64_t seq,
				  uint64_t sp_ts, const float sp_pos[3],
				  float px, float py, float pz,
				  const float u[4])
	{
		std::lock_guard<std::mutex> lock(_mutex);
		ensure_open();

		if (_fp != nullptr) {
			std::fprintf(_fp, "mcnn_pub,%llu,0,%lld,%llu,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,1\n",
				     static_cast<unsigned long long>(t_us),
				     static_cast<long long>(seq),
				     static_cast<unsigned long long>(sp_ts),
				     static_cast<double>(sp_pos[0]),
				     static_cast<double>(sp_pos[1]),
				     static_cast<double>(sp_pos[2]),
				     static_cast<double>(px),
				     static_cast<double>(py),
				     static_cast<double>(pz),
				     static_cast<double>(u[0]),
				     static_cast<double>(u[1]),
				     static_cast<double>(u[2]),
				     static_cast<double>(u[3]));

			if ((seq <= 5) || ((seq % 250) == 0)) {
				std::fflush(_fp);
			}
		}
	}

	Snapshot snapshot() const
	{
		Snapshot s{};
		const int64_t sess = _session_pub_count.load(std::memory_order_acquire);
		s.is_neural = (sess > 0) ? 1 : 0;
		s.pub_seq = (sess > 0) ? _pub_seq.load(std::memory_order_acquire) : 0;
		return s;
	}

	void record_gz_esc_pub(uint64_t t_us, const Snapshot &snap, const float outputs[4])
	{
		std::lock_guard<std::mutex> lock(_mutex);
		ensure_open();

		if (_fp != nullptr) {
			++_gz_pub_count;
			std::fprintf(_fp, "gz_esc_pub,%llu,0,%lld,0,0,0,0,0,0,0,%.4f,%.4f,%.4f,%.4f,%d\n",
				     static_cast<unsigned long long>(t_us),
				     static_cast<long long>(snap.pub_seq),
				     static_cast<double>(outputs[0]),
				     static_cast<double>(outputs[1]),
				     static_cast<double>(outputs[2]),
				     static_cast<double>(outputs[3]),
				     snap.is_neural);

			if ((_gz_pub_count % 250) == 0) {
				std::fflush(_fp);
			}
		}
	}

private:
	Observer() = default;

	~Observer()
	{
		std::lock_guard<std::mutex> lock(_mutex);

		if (_fp != nullptr) {
			std::fflush(_fp);
			std::fclose(_fp);
			_fp = nullptr;
		}
	}

	void ensure_open()
	{
		if (_init_done) {
			return;
		}

		_init_done = true;
		const char *path = std::getenv("MCNN_OBS_LOG");

		if (path != nullptr && path[0] != '\0') {
			_fp = std::fopen(path, "w");

			if (_fp != nullptr) {
				std::fprintf(_fp, "event,t_us,nav_or_mode,pub_seq,sp_ts,sp_x,sp_y,sp_z,pos_x,pos_y,pos_z,v0,v1,v2,v3,is_neural\n");
				std::fflush(_fp);
			}
		}
	}

	std::mutex _mutex;
	std::FILE *_fp{nullptr};
	bool _init_done{false};
	int64_t _gz_pub_count{0};
	std::atomic<int64_t> _pub_seq{0};
	std::atomic<int64_t> _session_pub_count{0};
};

} // namespace mcnn_obs

#endif // __PX4_POSIX
