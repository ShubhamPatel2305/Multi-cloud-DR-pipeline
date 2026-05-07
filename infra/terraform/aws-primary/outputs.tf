output "alb_dns_name" {
  description = "Public DNS name of the primary ALB. Add as origin in the Cloudflare load balancer pool."
  value       = aws_lb.this.dns_name
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.this.name
}

output "ecs_service_name" {
  value = aws_ecs_service.this.name
}

output "vpc_id" {
  value = aws_vpc.this.id
}
