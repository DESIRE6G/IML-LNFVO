#!/bin/bash
A=( $(basename -a /sys/class/net/*br*) )
base=$1

cmd="simple_switch_grpc --log-console --device-id 1"
for i in "${!A[@]}"; do
  cmd="${cmd} -i ${i}@${A[i]}"
done
cmd="${cmd} /src/${1}/data-plane/${1}.json -- --grpc-server-addr 0.0.0.0:50051"
$cmd
