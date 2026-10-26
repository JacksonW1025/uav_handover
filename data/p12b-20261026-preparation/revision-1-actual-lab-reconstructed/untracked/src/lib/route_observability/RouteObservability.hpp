/****************************************************************************
 *
 * Observation-only route event helper. No control code reads this topic.
 *
 ****************************************************************************/

#pragma once

#include <drivers/drv_hrt.h>
#include <uORB/PublicationMulti.hpp>
#include <uORB/topics/route_observability.h>

namespace route_observability
{

#if defined(ROUTE_OBSERVABILITY_TRANSITION)
static constexpr uint32_t expected_period_us = 8000;
static constexpr uint8_t profile = route_observability_s::PROFILE_TRANSITION;
#else
static constexpr uint32_t expected_period_us = 100000;
static constexpr uint8_t profile = route_observability_s::PROFILE_BASELINE;
#endif

inline void publish(uORB::PublicationMulti<route_observability_s> &publisher,
		    uint32_t &sequence, hrt_abstime &last_publication,
		    uint8_t event_type, uint8_t source_id, uint8_t topic_id,
		    uint8_t writer_id, uint64_t subject_timestamp, uint8_t instance = 0)
{
#if defined(ROUTE_OBSERVABILITY_OFF)
	(void)publisher; (void)sequence; (void)last_publication; (void)event_type; (void)source_id;
	(void)topic_id; (void)writer_id; (void)subject_timestamp; (void)instance;
	return;
#endif
	if (expected_period_us != 0 && hrt_elapsed_time(&last_publication) < expected_period_us) {
		return;
	}

	last_publication = hrt_absolute_time();
	route_observability_s observation{};
	observation.timestamp = last_publication;
	observation.subject_timestamp = subject_timestamp;
	observation.sequence = sequence++;
	observation.expected_period_us = expected_period_us;
	observation.event_type = event_type;
	observation.source_id = source_id;
	observation.topic_id = topic_id;
	observation.writer_id = writer_id;
	observation.profile = profile;
	observation.instance = instance;
	publisher.publish(observation);
}

inline uint32_t componentHash(const char *name)
{
	uint32_t hash = 2166136261u;

	for (const char *character = name; character != nullptr && *character != '\0'; ++character) {
		hash ^= static_cast<uint8_t>(*character);
		hash *= 16777619u;
	}

	return hash;
}

inline void publishRouteEpoch(uORB::PublicationMulti<route_observability_s> &publisher,
			       uint32_t &sequence, uint64_t route_epoch_id,
			       int8_t previous_nav_state, int8_t new_nav_state,
			       uint8_t change_source, int8_t registration_mode_id,
			       int8_t executor_in_charge, bool armed)
{
#if defined(ROUTE_OBSERVABILITY_OFF)
	(void)publisher; (void)sequence; (void)route_epoch_id; (void)previous_nav_state; (void)new_nav_state;
	(void)change_source; (void)registration_mode_id; (void)executor_in_charge; (void)armed;
	return;
#endif
	route_observability_s observation{};
	observation.timestamp = hrt_absolute_time();
	observation.subject_timestamp = observation.timestamp;
	observation.sequence = sequence++;
	observation.expected_period_us = 0;
	observation.route_epoch_id = route_epoch_id;
	observation.event_type = route_observability_s::EVENT_ROUTE_EPOCH_CHANGED;
	observation.profile = profile;
	observation.previous_nav_state = previous_nav_state;
	observation.new_nav_state = new_nav_state;
	observation.change_source = change_source;
	observation.registration_mode_id = registration_mode_id;
	observation.executor_in_charge = executor_in_charge;
	observation.armed = armed;
	publisher.publish(observation);
}

inline void publishLifecycle(uORB::PublicationMulti<route_observability_s> &publisher,
			      uint32_t &sequence, uint8_t event_type,
			      const char *component_name, int8_t mode_id,
			      int8_t executor_id, int8_t arming_check_id,
			      int8_t result, bool active_at_event,
			      int8_t fallback_nav_state,
			      uint8_t reason_code = route_observability_s::REASON_NONE,
			      uint64_t failed_check_mask = 0)
{
#if defined(ROUTE_OBSERVABILITY_OFF)
	(void)publisher; (void)sequence; (void)event_type; (void)component_name; (void)mode_id;
	(void)executor_id; (void)arming_check_id; (void)result; (void)active_at_event;
	(void)fallback_nav_state; (void)reason_code; (void)failed_check_mask;
	return;
#endif
	route_observability_s observation{};
	observation.timestamp = hrt_absolute_time();
	observation.subject_timestamp = observation.timestamp;
	observation.sequence = sequence++;
	observation.expected_period_us = 0;
	observation.failed_check_mask = failed_check_mask;
	observation.component_hash = componentHash(component_name);
	observation.event_type = event_type;
	observation.profile = profile;
	observation.registration_mode_id = mode_id;
	observation.executor_in_charge = executor_id;
	observation.arming_check_id = arming_check_id;
	observation.result = result;
	observation.reason_code = reason_code;
	observation.active_at_event = active_at_event;
	observation.fallback_nav_state = fallback_nav_state;
	publisher.publish(observation);
}

} // namespace route_observability
