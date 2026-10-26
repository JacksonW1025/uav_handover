/****************************************************************************
 *
 *   Copyright (c) 2023 PX4 Development Team. All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 *
 * 1. Redistributions of source code must retain the above copyright
 *	notice, this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright
 *	notice, this list of conditions and the following disclaimer in
 *	the documentation and/or other materials provided with the
 *	distribution.
 * 3. Neither the name PX4 nor the names of its contributors may be
 *	used to endorse or promote products derived from this software
 *	without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 * "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 * LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
 * FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
 * COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
 * INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
 * BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS
 * OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED
 * AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
 * LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
 * ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 * POSSIBILITY OF SUCH DAMAGE.
 *
 ****************************************************************************/

#include "GZMixingInterfaceESC.hpp"
#include <uORB/topics/research_output.h>
#include <time.h>

bool GZMixingInterfaceESC::init(const std::string &model_name)
{

	// ESC feedback: /x500/command/motor_speed
	std::string motor_speed_topic = "/" + model_name + "/command/motor_speed";

	if (!_node.Subscribe(motor_speed_topic, &GZMixingInterfaceESC::motorSpeedCallback, this)) {
		PX4_ERR("failed to subscribe to %s", motor_speed_topic.c_str());
		return false;
	}

	// output eg /X500/command/motor_speed
	std::string actuator_topic = "/" + model_name + "/command/motor_speed";
	_actuators_pub = _node.Advertise<gz::msgs::Actuators>(actuator_topic);

	if (!_actuators_pub.Valid()) {
		PX4_ERR("failed to advertise %s", actuator_topic.c_str());
		return false;
	}

	_esc_status_pub.advertise();


	ScheduleNow();

	return true;
}

bool GZMixingInterfaceESC::updateOutputs(float outputs[MAX_ACTUATORS], unsigned num_outputs, unsigned num_control_groups_updated)
{
	unsigned active_output_count = 0;

	for (unsigned i = 0; i < num_outputs; i++) {
		if (_mixing_output.isFunctionSet(i)) {
			active_output_count++;

		} else {
			break;
		}
	}

	if (active_output_count > 0) {
		gz::msgs::Actuators rotor_velocity_message;

		auto *vel = rotor_velocity_message.mutable_velocity();
		vel->Clear();
		vel->Reserve(active_output_count);

		for (unsigned i = 0; i < active_output_count; ++i) {
			vel->Add(static_cast<double>(outputs[i]));
		}

		if (_actuators_pub.Valid()) {
            // Sample ID travels to Gazebo in the header; the motor model ignores headers.
            const uint64_t research_sample=_mixing_output.researchSelectedSampleTimestamp();
            rotor_velocity_message.mutable_header()->mutable_stamp()->set_sec(research_sample/1000000ULL);
            rotor_velocity_message.mutable_header()->mutable_stamp()->set_nsec((research_sample%1000000ULL)*1000ULL);
            const bool published=_actuators_pub.Publish(rotor_velocity_message);
            // This confirms bridge selection and transport publication, NOT motor physics consumption.
            static uint64_t attempts=0, successes=0, repeated=0, regressed=0, negative=0, previous=0;
            static uint64_t bins[8]{};
            const uint64_t sample=_mixing_output.researchSelectedSampleTimestamp();
            const uint64_t now=hrt_absolute_time();
            const int64_t age=static_cast<int64_t>(now)-static_cast<int64_t>(sample);
            ++attempts;if(published)++successes;
            if(sample && previous==sample)++repeated;
            if(sample && previous && sample<previous)++regressed;
            if(sample) {
                previous=sample;
                if(age<0)++negative;
                else {
                    const int64_t limits[7]={0,4000,8000,12000,20000,40000,100000};
                    unsigned i=0;while(i<7 && age>limits[i])++i;++bins[i];
                }
            }
            struct timespec wall{};clock_gettime(CLOCK_MONOTONIC,&wall);
            research_output_s trace{};
            trace.timestamp=now;trace.timestamp_sample=sample;
            trace.wall_monotonic_ns=static_cast<uint64_t>(wall.tv_sec)*1000000000ULL+wall.tv_nsec;
            trace.attempts_total=attempts;trace.published_total=successes;
            trace.repeated_sample_total=repeated;trace.regressed_sample_total=regressed;trace.negative_age_total=negative;
            for(unsigned i=0;i<8;i++)trace.age_bins[i]=bins[i];
            trace.transport_published=published;trace.armed=_mixing_output.armed().armed;
            static uint64_t skipped=0;static unsigned previous_generation=0;static bool generation_seen=false;
            unsigned generation=0;
            if(_mixing_output.researchSelectedGeneration(generation)) {
                if(generation_seen && generation!=previous_generation)skipped+=generation-previous_generation-1;
                previous_generation=generation;generation_seen=true;
            }
            trace.skipped_publication_total=skipped;
            for(unsigned i=0;i<4 && i<active_output_count;i++)trace.motor_speed[i]=outputs[i];
            static uORB::Publication<research_output_s> trace_pub{ORB_ID(research_output)};
            trace_pub.publish(trace);
            return published;
		}
	}

	return false;
}

void GZMixingInterfaceESC::Run()
{
	pthread_mutex_lock(&_node_mutex);
	_mixing_output.update();
	_mixing_output.updateSubscriptions(false);
	pthread_mutex_unlock(&_node_mutex);
}

void GZMixingInterfaceESC::motorSpeedCallback(const gz::msgs::Actuators &actuators)
{
	if (hrt_absolute_time() == 0) {
		return;
	}

	pthread_mutex_lock(&_node_mutex);

	esc_status_s esc_status{};
	int limited_escs = math::min(actuators.velocity_size(), (int)esc_status_s::CONNECTED_ESC_MAX);
	esc_status.esc_count = limited_escs;

	for (int i = 0; i < limited_escs; i++) {
		esc_status.esc[i].timestamp = hrt_absolute_time();
		esc_status.esc[i].esc_rpm = actuators.velocity(i);
		esc_status.esc[i].esc_temperature = 50.f; // arbitrary, fixed ESC temperature
		esc_status.esc_online_flags |= 1 << i;
		esc_status.esc[i].actuator_function = (uint8_t)_mixing_output.outputFunction(i);

		// This is a race condition with the failure detector, for smaller models it always resolves before
		// the failure detector runs, but for larger models (with more than 8 ESCs) the failure detector
		// can run before the velocity of some escs is set > 0. To mitigate this, if one esc has a velocity > 0,
		// we assume all escs are armed.
		if (actuators.velocity(i) > 0) {
			esc_status.esc_armed_flags = (1 << limited_escs) - 1;
		}
	}

	if (esc_status.esc_count > 0) {
		esc_status.timestamp = hrt_absolute_time();
		_esc_status_pub.publish(esc_status);
	}

	pthread_mutex_unlock(&_node_mutex);
}
