variable "aws_region" {
  type    = string
  default = "ap-southeast-1"
}

variable "vpc_cidr" {
  type    = string
  default = "10.30.0.0/16"
}

variable "az_count" {
  type    = number
  default = 2
}

variable "image_uri" {
  type = string
}

variable "service_desired_count" {
  description = "Hot standby - kept warm at lower capacity. Auto-scales on takeover."
  type        = number
  default     = 1
}

variable "task_cpu" {
  type    = number
  default = 512
}

variable "task_memory" {
  type    = number
  default = 1024
}

variable "mongo_uri_arn" {
  type = string
}
