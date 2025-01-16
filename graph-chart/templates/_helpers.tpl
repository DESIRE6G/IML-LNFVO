{{/* Generate basic L2 bridge */}}
{{- define "nfrouter.l2bridge" }}
apiVersion: "k8s.cni.cncf.io/v1"
kind: NetworkAttachmentDefinition
metadata:
  name: {{ .id }}
spec:
  config: '{
      "cniVersion": "0.3.0",
      "plugins": [
        {
          "name": "{{ .id }}",
          "type": "bridge",
          "bridge": "{{ .id }}",
          "ipam": {}
        }, {
          "capabilities": { "mac": true },
          "type": "tuning"
        }
      ]
    }'
{{- end }}

{{/* Generate memif bridge */}}
{{- define "nfrouter.memif" }}
apiVersion: "k8s.cni.cncf.io/v1"
kind: NetworkAttachmentDefinition
metadata:
  name: {{ .id }}
spec:
  config: '{
      "cniVersion": "0.3.1",
      "type": "userspace",
      "name": "{{ .id }}",
      "kubeconfig": "/etc/cni/net.d/multus.d/multus.kubeconfig",
      "logFile": "/var/log/{{ .id }}-cni.log",
      "logLevel": "debug",
      "host": {
              "engine": "vpp",
              "iftype": "memif",
              "netType": "bridge",
              "memif": {
                      "role": "master",
                      "mode": "ethernet"
              },
              "bridge": {
                      "bridgeName": "{{ .if.bridgedomain }}"
              }
      },
      "container": {
              "engine": "vpp",
              "iftype": "memif",
              "netType": "interface",
              "memif": {
                      "role": "slave",
                      "mode": "ethernet"
              }
      }
    }'
{{- end }}

{{/* Generate basic sriov VF device */}}
{{- define "nfrouter.sriov-vf" }}
apiVersion: "k8s.cni.cncf.io/v1"
kind: NetworkAttachmentDefinition
metadata:
  name: {{ .id }}
  annotations:
        k8s.v1.cni.cncf.io/resourceName: {{ .if.vf }}
spec:
  config: '{
      "cniVersion": "0.3.0",
      "type": "sriov",
      "name": "{{ .id }}",
      "mac": "{{ .if.mac }}"
    }'
{{- end }}

{{/* Generate kustomization for the configs */}}
{{- define "nfrouter.configs-kustomization" }}
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
metadata:
  name: configs

resources:
{{- range $id, $nf := . }}
{{- if hasKey $nf "files" }}
- {{ $id }}-config.yml
{{- end }}
{{- end }}
{{- end }}

{{/* Generate kustomization for the interfaces */}}
{{- define "nfrouter.interfaces-kustomization" }}
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
metadata:
  name: interfaces

resources:
{{- range $id, $if := . }}
- {{ $id }}.yml
{{- end }}
{{- end }}

{{/* Generate kustomize patch for nf */}}
{{- define "nfrouter.nf-kustomize-patch" }}
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
metadata:
  name: {{ .id }}

resources:
- ../../services/{{ .nf.name }}
patches:
- target:
    kind: Deployment
  patch: |-
    - op: replace
      path: /metadata/name
      value: {{ .id }}
- patch: |-
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: {{ .id }}
    spec:
      selector:
        matchLabels:
          app: {{ .id }}
      template:
        metadata:
          labels:
            app: {{ .id }}
          annotations:
            k8s.v1.cni.cncf.io/networks: '{{ .nf.interfaces | toJson }}'
        spec:
          nodeName: {{ .nf.node }}
          containers:
          - name: {{ .nf.name }}
          {{- if hasKey .nf "cmd" }}
            args: [ '{{ .nf.cmd }}' ]
          {{- end }}
          {{- if or (hasKey .nf "files") (hasKey .nf "hostpath") }}
            volumeMounts:
          {{- end }}
          {{- if hasKey .nf "files" }}
              - name: nf-config
                mountPath: /opt/nfconfig
          {{- end }}
          {{- if hasKey .nf "hostpath" }}
              - name: {{ .nf.hostpath.name }}
                mountPath: {{ .nf.hostpath.path }}
          {{- end }}
          {{- if hasKey .nf "initcmd" }}
          initContainers:
          - name: init-network
            image: {{ .nf.initimage }}
            securityContext:
              privileged: true
            command: ['sh', '-c', '{{ .nf.initcmd }}']
          {{- end }}
          {{- if or (hasKey .nf "files") (hasKey .nf "hostpath") }}
          volumes:
          {{- end }}
          {{- if hasKey .nf "files" }}
          - name: nf-config
            configMap:
              name: {{ .id }}-config
          {{- end }}
          {{- if (hasKey .nf "hostpath") }}
          - name: {{ .nf.hostpath.name }}
            hostPath:
              path: {{ .nf.hostpath.hostpath }}
          {{- end }}

{{- end }}

{{/* Generate configmap for files */}}
{{- define "nfrouter.nf-files-configmap" }}
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ .id }}-config
data:
  {{ .files | toJson }}
{{- end }}

{{/* Generate kustomization for the deployment */}}
{{- define "nfrouter.kustomization" }}
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
metadata:
  name: main

resources:
- interfaces
- configs
{{- range $id, $service := . }}
- {{ $id }}
{{- end }}
{{- end }}

