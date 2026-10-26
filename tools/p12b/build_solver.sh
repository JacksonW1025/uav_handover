#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
g++ -std=c++17 -O2 -DNDEBUG -fPIC -shared -Wall -Wextra -Werror -Wl,-z,defs \
 -isystem data/p12b-20261026-source-local/headers/usr/include -isystem /usr/include/eigen3 \
 research/solver/P12bDartTrace.cpp /usr/lib/aarch64-linux-gnu/libdart.so.6.13.2 \
 /usr/lib/aarch64-linux-gnu/libgz-math7.so.7 -ldl \
 -o data/p12b-20261026-source-local/libP12bDartTrace.so
