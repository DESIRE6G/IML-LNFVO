#!/bin/bash

DIR=./kustomize
ALL=all.yml
FN=$DIR/$ALL

mkdir -p $DIR
cat <&0 > $FN
kubectl slice -f $FN --include Kustomization/main -t kustomization.yml -o $DIR
kubectl slice -f $FN --include-kind "NetworkAttachmentDefinition" -t {{.metadata.name}}.yml -o $DIR/interfaces
kubectl slice -f $FN --include-kind "ConfigMap" -t {{.metadata.name}}.yml -o $DIR/configs
for nf in $(yq -r 'select(.kind == "Kustomization" and .metadata.name != "main").metadata.name' $FN); do
  kubectl slice -f $FN --include Kustomization/$nf -t kustomization.yml -o $DIR/$nf
done
kubectl kustomize $DIR && rm -rf $DIR
