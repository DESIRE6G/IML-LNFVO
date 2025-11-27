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

{{/* Generate macvlan */}}
{{- define "nfrouter.macvlan" }}
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
          "type": "macvlan",
          "master": "{{ .if.master }}",
          "mode": "bridge",
          "ipam": {}
        }, {
          "capabilities": { "mac": true },
          "type": "tuning"
        }
      ]
    }'
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

{{- if or (hasKey .nf "files") }}
configMapGenerator:
- name: {{ .id }}-config
  files:
{{- range .nf.files }}
  - {{ .path }}
{{- end }}
{{- end }}

resources:
- ../../apps/{{ .nf.name }}
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
          {{- if hasKey .nf "image" }}
            image: {{ .nf.image }}
          {{- end }}
          {{- if hasKey .nf "cmd" }}
            args: [ '{{ .nf.cmd }}' ]
          {{- end }}
          {{- if hasKey .nf "vfres" }}
            resources:
              requests:
                {{ .nf.vfres }}: '1'
              limits:
                {{ .nf.vfres }}: '1'
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
          {{- if .nf.env }}
            env:
            {{- range $key, $val := .nf.env }}
            - name: {{ $key }}
              value: {{ $val | quote }}
            {{- end }}
          {{- end }}
          {{- if or (hasKey .nf "initcmd") (hasKey .nf "sidecar") }}
          initContainers:
          {{- end }}
          {{- if hasKey .nf "initcmd" }}
          - name: init-network
            image: {{ .nf.initimage }}
            imagePullPolicy: Never
            securityContext:
              privileged: true
            command: ['sh', '-c', '{{ .nf.initcmd }}']
          {{- end }}
          {{- if hasKey .nf "sidecar" }}
          - name: switch
            image: {{ .nf.sidecar.image }}
            imagePullPolicy: Never
            restartPolicy: Always
            securityContext:
              privileged: true
            command: ['sh', '-c', '{{ .nf.sidecar.cmd }}']
          {{- if hasKey .nf "files" }}
            volumeMounts:
              - name: nf-config
                mountPath: /opt/nfconfig
          {{- end }}
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

{{/* Generate kustomization for the deployment */}}
{{- define "nfrouter.kustomization" }}
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
metadata:
  name: main

resources:
- interfaces
{{- range $id, $service := . }}
- {{ $id }}
{{- end }}
{{- end }}

