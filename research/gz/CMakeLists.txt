# Research copy of gz-sim 8.11.0 MulticopterMotorModel with per-step trace only.
project(ResearchMulticopterMotorModel)
add_library(${PROJECT_NAME} SHARED ResearchMulticopterMotorModel.cc)
target_link_libraries(${PROJECT_NAME}
    PUBLIC ${GZ_PLUGIN_TARGET}
    PUBLIC ${GZ_SIM_TARGET}
    PUBLIC ${GZ_TRANSPORT_TARGET}
)
target_include_directories(${PROJECT_NAME} PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
