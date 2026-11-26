cmake_minimum_required(VERSION 3.16)
project(mcnn_motor_relay_plugin LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(PkgConfig REQUIRED)
pkg_check_modules(GZ_SIM REQUIRED IMPORTED_TARGET gz-sim8)
pkg_check_modules(GZ_TRANSPORT REQUIRED IMPORTED_TARGET gz-transport13)
pkg_check_modules(GZ_MSGS REQUIRED IMPORTED_TARGET gz-msgs10)
pkg_check_modules(GZ_PLUGIN REQUIRED IMPORTED_TARGET gz-plugin2)

add_library(McnnMotorRelayPlugin SHARED McnnMotorRelayPlugin.cc)
target_link_libraries(McnnMotorRelayPlugin
  PRIVATE
    PkgConfig::GZ_SIM
    PkgConfig::GZ_TRANSPORT
    PkgConfig::GZ_MSGS
    PkgConfig::GZ_PLUGIN
)
