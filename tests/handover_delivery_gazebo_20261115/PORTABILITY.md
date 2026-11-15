# 复现材料与记录范围

as-run-sha256.json保留原运行材料SHA-256；原文件留在Thor，未覆盖。发布版脚本使用显式路径参数，provenance/evidence仅去除本机绝对路径，world为插件路径模板。它们是后续可移植整理，不是当时原样执行的文件。recorded结果未重新跑仿真。

此次只对可移植Python做语法检查，并对Gazebo两份32步原始bin用标准库只读分析复核。没有执行可移植runner、没有新Gazebo或飞行。需要匹配Gazebo Harmonic/gz-msgs10/gz-transport13开发库及原插件版本；基线仓库不携带后期插件。

primitive: python3 build_test.py --source <匹配SHA的插件源码> --output <新目录> 仅抽取生成代码；用g++链接gz-msgs10并启用ASan/UBSan可运行组件测试。

gazebo: 编译driver.cpp后，python3 run.py --plugin <匹配SHA的.so> --driver <编译后driver> --output <新目录>。它会启动Gazebo，勿与飞行实验并发。python3 analyze.py --input <已有结果目录> 是只读无仿真检查。

C/N为合成身份标记；不从marker计算命令年龄，不推断四电机或闭环危险性。
