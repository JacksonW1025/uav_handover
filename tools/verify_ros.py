#!/usr/bin/env python3
"""Validate native message support, a live local pub/sub, and overlay separation."""
import importlib
import json
import os
from pathlib import Path
import sys
import time
import rclpy
from rclpy.qos import qos_profile_sensor_data
import px4_msgs.msg as msgs
from rosidl_generator_py import import_type_support
ROOT=Path(__file__).resolve().parents[1]
variant=os.environ['HANDOVER_VARIANT'];out=ROOT/'data/environment-20261009'/('ros-'+variant+'-verification.json')
result={'variant':variant,'checks':{},'message_fields':{},'python':sys.executable}
for name in ['VehicleStatus','VehicleCommand','VehicleCommandAck','VehicleOdometry','OffboardControlMode','TrajectorySetpoint']:
 typ=getattr(msgs,name);typ.__class__.__import_type_support__()
 if typ.__class__._TYPE_SUPPORT is None:raise RuntimeError(name+' has no native type support')
 result['message_fields'][name]={'version':getattr(typ,'MESSAGE_VERSION',0),'fields':typ.get_fields_and_field_types()}
path=Path(importlib.import_module('px4_msgs').__file__).resolve()
assert str(ROOT/'uav_lab/workspaces'/variant/'install') in str(path),path
result['checks']['overlay_isolation']='PASS';result['package_path']=str(path)
rclpy.init();node=rclpy.create_node('lab_message_probe_'+variant)
received=[];topic='/handover_lab_probe/'+variant
sub=node.create_subscription(msgs.VehicleCommand,topic,lambda m:received.append(m),qos_profile_sensor_data)
pub=node.create_publisher(msgs.VehicleCommand,topic,10)
msg=msgs.VehicleCommand();msg.timestamp=12345678;msg.command=176;msg.param1=1.25
end=time.monotonic()+8
while time.monotonic()<end and not received:
 pub.publish(msg);rclpy.spin_once(node,timeout_sec=.1)
assert received and received[-1].timestamp==12345678 and received[-1].param1==1.25
result['checks']['local_pubsub']='PASS';result['checks']['native_typesupport']='PASS'
node.destroy_node();rclpy.shutdown();out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
