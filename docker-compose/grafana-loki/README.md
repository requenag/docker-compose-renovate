# Loki Promtail Grafana

## About this Procedure

This procedure details how to install `Loki` `Promtail` and `Grafana` using `docker-compose`.

Loki, Promtail, and Grafana provide an efficient stack for managing and visualizing logs. Loki is a log aggregation system designed for scalability and ease of use, similar to Prometheus but for logs. Promtail is an agent that collects logs from various sources (such as systemd journals or log files) and forwards them to Loki. Grafana is used to query and visualize these logs through an intuitive dashboard, enabling real-time monitoring and analysis. This combination offers a cost-effective, cloud-native solution for centralized log management without the need for complex indexing.

For Windows Standard Operating Environments (SOEs), Fluent Bit is particularly useful as it can parse Windows Event Logs, transform them into structured data, and send clear, organized logs to Loki. 

For Linux SOEs, Promtail is the preferred agent, efficiently collecting system logs, application logs, and custom log files for transmission to Loki

For Kubernetes and related container platform services (e.g. Openshift, RKE2), promtail is deployed as `DeemonSet` to collect and ship logs from kubernetes nodes. To avoid to collect a large set of logs, dedicated namespace can be monitored.

Security around logs shipment can be achieve by using TLS certificate with a trusted CA/SubCA and authentication at Grafana/Loki interface level. (to be implemented)

### Set permission for promtail

To allow permission to access to logs file, you can use the following commands below on Linux SOEs:

```bash
systemctl stop promtail
sudo adduser --system promtail
sudo usermod -a -G systemd-journal promtail
cd /var
sudo chown promtail:promtail /tmp/positions.yaml
sudo setfacl -R -m u:promtail:rX log
sudo setfacl -R -m d:u:promtail:rX log
systemctl enable promtail --now
```

## Reference

* [Fluent-bit on Windows](https://blog.e-mundo.de/post/painless-and-secure-windows-event-log-delivery-with-fluent-bit-loki-and-grafana/)