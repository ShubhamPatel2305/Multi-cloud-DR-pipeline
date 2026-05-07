variable "aws_region" {
  type    = string
  default = "ap-south-1"
}

variable "vpc_cidr" {
  type    = string
  default = "10.20.0.0/16"
}

variable "az_count" {
  type    = number
  default = 2
}

variable "image_uri" {
  description = "ECR image URI for the dr-demo-api container"
  type        = string
}

variable "service_desired_count" {
  type    = number
  default = 3
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
  description = "ARN of the SecretsManager secret holding the MongoDB Atlas URI"
  type        = string
}

variable "log_retention_days" {
  type    = number
  default = 14
}
