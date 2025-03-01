# Loki Promtail Grafana

## About this Procedure

This procedure details how to install Loki Promtail Grafana using dokker-compose.

Loki, Promtail, and Grafana provide an efficient stack for managing and visualizing logs. Loki is a log aggregation system designed for scalability and ease of use, similar to Prometheus but for logs. Promtail is an agent that collects logs from various sources (such as systemd journals or log files) and forwards them to Loki. Grafana is used to query and visualize these logs through an intuitive dashboard, enabling real-time monitoring and analysis. This combination offers a cost-effective, cloud-native solution for centralized log management without the need for complex indexing.

For Windows Standard Operating Environments (SOEs), Fluent Bit is particularly useful as it can parse Windows Event Logs, transform them into structured data, and send clear, organized logs to Loki. 

For Linux SOEs, Promtail is the preferred agent, efficiently collecting system logs, application logs, and custom log files for transmission to Loki

Security around log shipment can be achieve by using TLS certificate with a trusted CA/SubCA.


### Set permission for promtail

```bash
usermod -a -G systemd-journal promtail
usermod -a -G adm promtail
sudo setfacl -R -m u:promtail:rX /var/log/
sudo setfacl -R -m u:promtail:rX /var/log/*
sudo setfacl -R -m u:promtail:rX /var/log/audit/
sudo setfacl -R -m u:promtail:rX /var/log/audit/*
chown promtail:promtail /tmp/positions.yaml
systemctl restart promtail
```

## Reference

* [Fluent-bit on Windows](https://blog.e-mundo.de/post/painless-and-secure-windows-event-log-delivery-with-fluent-bit-loki-and-grafana/)