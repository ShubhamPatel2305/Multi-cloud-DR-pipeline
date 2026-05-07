# Cloudflare load-balancer stack

This stack defines the production traffic-steering layer:

- One health monitor (`/health/deep`)
- Three pools, one per cloud region
- A load balancer with strict pool ordering (no geo-steering)

## Failover

Cloudflare promotes the next pool in `default_pool_ids` whenever the current
pool's `minimum_origins` is no longer met. The monitor is shared so all three
pools probe the same endpoint with the same expected response.

## Failback (the part you can't fully express in Terraform)

Cloudflare's load balancer doesn't support an automated stepped percentage
ramp on a single pool — pool ordering is binary. The repo handles this with
an out-of-band controller (see `router/src/canary.py` in the simulator) which
in production drives `cloudflare_load_balancer_pool` weights through the API:

1. Hold the recovered primary at weight 0 (still in pool, not receiving traffic).
2. Verify HEALTHY from the monitor for >=N consecutive cycles.
3. Bump weight to 5 → 25 → 50 → 100 with a hold window between each step.
4. Roll back to 0 if the monitor flips during any hold window.

The Terraform `weight` attribute is intentionally left at `1` here — the
canary controller writes weights at runtime and Terraform should not fight
that state. Use `lifecycle.ignore_changes = [origins]` if you re-apply
during a canary run.

## Variables

`primary_origin`, `standby_origin`, `dr_origin` come from the outputs of the
three regional stacks. Wire them through with a thin root module or
Terragrunt — the regional and edge stacks intentionally don't share state.
