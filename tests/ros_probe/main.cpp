#include <rclcpp/rclcpp.hpp>
#include <px4_msgs/msg/vehicle_command.hpp>
#ifdef HAVE_PX4_INTERFACE
#include <px4_ros2/components/mode.hpp>
#endif
#include <chrono>
int main(int argc,char **argv) {
 rclcpp::init(argc,argv);auto n=std::make_shared<rclcpp::Node>("handover_cpp_probe");
 bool received=false;
 auto sub=n->create_subscription<px4_msgs::msg::VehicleCommand>("/handover_cpp_probe",10,[&](const px4_msgs::msg::VehicleCommand &m){received=m.command==176 && m.timestamp==123456;});
 auto pub=n->create_publisher<px4_msgs::msg::VehicleCommand>("/handover_cpp_probe",10);
 px4_msgs::msg::VehicleCommand msg;msg.command=176;msg.timestamp=123456;
 auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(8);
 while(!received && std::chrono::steady_clock::now()<deadline){pub->publish(msg);rclcpp::spin_some(n);std::this_thread::sleep_for(std::chrono::milliseconds(20));}
 rclcpp::shutdown();return received?0:1;
}
