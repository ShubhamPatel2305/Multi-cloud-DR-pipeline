# Health check matrix

Three probe endpoints, each with a different cost and a different consumer.
Mixing them up is the most common cause of bad failover decisions.

## /health/live

**Purpose.** "Is this process alive?"

**Consumer.** Container orchestrator (ECS, Kubernetes, Container Apps).

**Cost.** Cheap. No I/O, no dependency reach.

**What 200 means.** The HTTP server is accepting connections.

**What 200 does not mean.** The instance is ready for traffic. Don't use
this for load-balancer pool membership.

## /health/ready

**Purpose.** "Should this instance receive traffic?"

**Consumer.** Load balancer (ALB target group, Cloudflare pool).

**Cost.** Light. Pings the database with a 1s timeout.

**What 200 means.** The instance can serve a typical request — process is
healthy AND the database is reachable from this region.

**What 503 means.** Pull this instance out of rotation until it goes back
to 200 for `healthy_threshold` consecutive probes.

**What it doesn't check.** Downstream third parties (payment gateway,
object storage). Including those in `/ready` would cause unnecessary
region failovers when a third party briefly hiccups, since *every*
region depends on the same third parties.

## /health/deep

**Purpose.** "Is this entire region serving real traffic correctly?"

**Consumer.** Cloudflare load-balancer monitor (or the mock router in
this repo).

**Cost.** Expensive. Reaches out to all critical dependencies. Gated to
a slower probe interval.

**What it checks.**

| Check | Why |
|-------|-----|
| Mongo Atlas reachability | Without DB, this region serves errors |
| Object storage | Many endpoints serve user-uploaded files |
| Payment gateway | Critical for one user-visible flow |
| CDN origin | Streaming pipeline depends on it |

**What 503 means.** Don't just pull this instance — pull the whole
region. Other instances in the same region likely have the same problem
(shared dependencies fail at the regional level, not the pod level).

## Threshold rationale

| Setting | Value | Why |
|---------|-------|-----|
| `unhealthy_threshold` | 2 | One probe loss is noise. Two is signal. |
| `healthy_threshold`   | 2 | Prevents region from flapping in and out during partial recovery. |
| `/ready` interval     | 5–10s | Tight enough that ALB de-registration happens fast. |
| `/deep` interval      | 30s  | Cloudflare LB plan minimum. Probing every 5s would be ideal. |

## Why three endpoints, not one

A single `/healthz` collapses three different decisions into one:

- "Restart this container" (live)
- "Stop sending requests to this pod" (ready)
- "Move all users to a different region" (deep)

Conflating them means a transient DB blip causes container restarts,
which does not help. Or it means a fully degraded region keeps serving
because the cheap probe still returns 200. Either way, you get the
wrong action at the wrong scope.
