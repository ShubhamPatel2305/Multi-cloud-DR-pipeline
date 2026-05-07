variable "cloudflare_api_token" {
  type      = string
  sensitive = true
}

variable "zone_id" {
  type = string
}

variable "account_id" {
  type = string
}

variable "domain" {
  description = "Hostname being load-balanced, e.g. api.example.com"
  type        = string
}

variable "primary_origin" {
  description = "Public DNS of the AWS Mumbai ALB"
  type        = string
}

variable "standby_origin" {
  description = "Public DNS of the AWS Singapore ALB"
  type        = string
}

variable "dr_origin" {
  description = "Public FQDN of the Azure Container Apps ingress"
  type        = string
}

variable "notification_email" {
  type    = string
  default = ""
}
