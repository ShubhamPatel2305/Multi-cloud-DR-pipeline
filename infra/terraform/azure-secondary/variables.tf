variable "location" {
  type    = string
  default = "centralindia"
}

variable "resource_group_name" {
  type    = string
  default = "rg-dr-secondary"
}

variable "image_name" {
  description = "Container image (registry/name:tag) pulled by the Container App"
  type        = string
}

variable "min_replicas" {
  description = "Cold-warm: kept at 1 to avoid full cold-start during failover"
  type        = number
  default     = 1
}

variable "max_replicas" {
  type    = number
  default = 6
}

variable "mongo_uri" {
  description = "MongoDB Atlas connection string. In real deployments this is sourced from Key Vault."
  type        = string
  sensitive   = true
}
