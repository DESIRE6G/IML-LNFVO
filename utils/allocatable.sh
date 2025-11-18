#!/bin/bash

kubectl get nodes -o 'jsonpath={.items[*].status.allocatable}' | jq -s 'map(to_entries) | flatten | group_by(.key) | map({key: .[0].key, value: map(.value | rtrimstr("Gi") | rtrimstr("Ki")
| tonumber) | add}) | from_entries'
