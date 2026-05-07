# Cloudflare load balancer is the production analogue of the mock router in
# this repo. The pool definitions and failover order encode the same
# active-passive policy: pool ordering is the failover priority.

resource "cloudflare_load_balancer_monitor" "deep_health" {
  account_id     = var.account_id
  type           = "https"
  method         = "GET"
  path           = "/health/deep"
  expected_codes = "200"
  interval       = 30
  timeout        = 5
  retries        = 2
  description    = "Deep health probe — DB + critical dependencies"
  header = {
    "Host" = [var.domain]
  }
  allow_insecure   = false
  follow_redirects = false
}

resource "cloudflare_load_balancer_pool" "primary" {
  account_id = var.account_id
  name       = "pool-aws-mumbai"
  monitor    = cloudflare_load_balancer_monitor.deep_health.id

  origins {
    name    = "aws-mumbai-alb"
    address = var.primary_origin
    enabled = true
    weight  = 1
  }

  notification_email = var.notification_email
  minimum_origins    = 1
}

resource "cloudflare_load_balancer_pool" "standby" {
  account_id = var.account_id
  name       = "pool-aws-singapore"
  monitor    = cloudflare_load_balancer_monitor.deep_health.id

  origins {
    name    = "aws-singapore-alb"
    address = var.standby_origin
    enabled = true
    weight  = 1
  }

  notification_email = var.notification_email
  minimum_origins    = 1
}

resource "cloudflare_load_balancer_pool" "dr" {
  account_id = var.account_id
  name       = "pool-azure-secondary"
  monitor    = cloudflare_load_balancer_monitor.deep_health.id

  origins {
    name    = "azure-secondary-app"
    address = var.dr_origin
    enabled = true
    weight  = 1
  }

  notification_email = var.notification_email
  minimum_origins    = 1
}

resource "cloudflare_load_balancer" "this" {
  zone_id = var.zone_id
  name    = var.domain
  proxied = true

  default_pool_ids = [
    cloudflare_load_balancer_pool.primary.id,
    cloudflare_load_balancer_pool.standby.id,
    cloudflare_load_balancer_pool.dr.id,
  ]

  fallback_pool_id = cloudflare_load_balancer_pool.dr.id

  steering_policy = "off"   # strict failover order, no geo split
  session_affinity = "none"

  description = "Active-passive multi-cloud DR. Failover order: primary → standby → dr."
}
