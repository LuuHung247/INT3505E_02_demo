# Monitoring Stack with Prometheus, Grafana, Node Exporter, cAdvisor, and Alertmanager

## 1. Chạy Prometheus bằng Docker

```bash
docker run -d --name=prometheus \
  -p 9090:9090 \
  -v $(pwd)/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml \
  prom/prometheus
```

- Truy cập giao diện Prometheus: [http://localhost:9090](http://localhost:9090)

---

## 2. Chạy Grafana bằng Docker

```bash
docker run -d --name=grafana \
  -p 3000:3000 \
  grafana/grafana
```

- Truy cập giao diện Grafana: [http://localhost:3000](http://localhost:3000)
- Mặc định user/password: `admin/admin`

---

## 3. Chạy Node Exporter bằng Docker

```bash
docker run -d --name=node_exporter \
  -p 9100:9100 \
  prom/node-exporter
```

- Kiểm tra dữ liệu Node Exporter: [http://localhost:9100/metrics](http://localhost:9100/metrics)

---

## 4. Reload Prometheus config

```bash
curl -X POST http://localhost:9090/-/reload
```

---

## 5. Chạy Alertmanager bằng Docker

```bash
docker run -d --name=alertmanager \
  -p 9093:9093 \
  -v $(pwd)/alertmanager.yml:/etc/alertmanager/alertmanager.yml \
  prom/alertmanager
```

- Truy cập giao diện Alertmanager: [http://localhost:9093](http://localhost:9093)

---

## 6. Chạy cAdvisor bằng Docker

```bash
docker run -d -p 8080:8080 \
  --volume=/:/rootfs:ro \
  --volume=/var/run:/var/run:ro \
  --volume=/sys:/sys:ro \
  --volume=/var/lib/docker/:/var/lib/docker:ro \
  gcr.io/cadvisor/cadvisor:latest
```

- Truy cập cAdvisor: [http://localhost:8080](http://localhost:8080)

---

## 7. Chạy tất cả dịch vụ bằng Docker Compose

```bash
docker compose up -d
```

- Bao gồm: `book_api`, `prometheus`, `grafana`, `node_exporter`, `cadvisor`, `alertmanager`

---

## 8. Một số query Prometheus cơ bản

### 8.1 Kiểm tra target có đang “up”:

```promql
up
```

### 8.2 CPU usage host (Node Exporter):

```promql
100 - (avg by(instance)(irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)
```

### 8.3 Memory usage host (Node Exporter):

```promql
(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100
```

### 8.4 Disk usage host (Node Exporter):

```promql
100 - (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"} * 100)
```

### 8.5 Network traffic host (Node Exporter):

```promql
sum(rate(node_network_receive_bytes_total[5m])) by (instance)
sum(rate(node_network_transmit_bytes_total[5m])) by (instance)
```

### 8.6 CPU usage container (cAdvisor):

```promql
sum(rate(container_cpu_usage_seconds_total[5m])) by (container_label_com_docker_swarm_service_name)
```

### 8.7 Memory usage container (cAdvisor):

```promql
sum(container_memory_usage_bytes) by (container_label_com_docker_swarm_service_name)
```

### 8.8 Docker container count:

```promql
count(container_last_seen) by (container_label_com_docker_swarm_service_name)
```

### 8.9 Kiểm tra request Flask API (nếu instrumented):

```promql
sum(rate(http_requests_total[5m])) by (method, endpoint)
```

> Lưu ý: metric `http_requests_total` chỉ có nếu Flask API được instrument với `prometheus_client`.
