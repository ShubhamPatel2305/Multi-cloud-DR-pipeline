output "alb_dns_name" {
  description = "Public DNS name of the standby ALB. Add as origin in the Cloudflare load balancer pool with priority 2."
  value       = aws_lb.this.dns_name
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.this.name
}

output "ecs_service_name" {
  value = aws_ecs_service.this.name
}
