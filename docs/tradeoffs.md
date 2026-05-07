# Trade-offs

Things this design gives up. The honest accounting.

## We accept some data loss on a forced primary election

A write acknowledged to the client microseconds before the Atlas primary
loses quorum can be rolled back. Practical RPO is on the order of
hundreds of milliseconds, but the worst-case bound is the oplog flush
window. For a payments system this would be unacceptable; for class
enrolment and progress tracking, it was.

If you're cloning this design for a workload where any data loss is too
much, you need synchronous cross-region writes (which means active-active
with conflict resolution, which is a much heavier system).

## Active-passive means the standby capacity is mostly idle

We pay for one warm pod in Singapore and one in Azure full-time. They
serve almost no real traffic during normal operation. This is a deliberate
cost — without it, takeover RTO would include container cold-start time
(~30–60s for our images), which would put us over the 90s target.

If RTO didn't matter, we'd scale standby to zero and pay nothing. If
operating budget didn't matter, we'd scale standby to full capacity all
the time and have a flat-line takeover. We picked a middle point — one
warm pod, then auto-scale on takeover.

## Cross-cloud egress is expensive

When traffic moves from AWS to Azure, both ends bill us for cross-cloud
data transfer. During a regional outage on AWS this is unavoidable; but
during a *test* drill, running the drill against the cross-cloud path
costs real money. We mitigate by:

- Running drills against the AWS-to-AWS failover (cheap)
- Running cross-cloud drills only quarterly
- Capping the drill duration at five minutes

## Cloudflare as a hard dependency

If Cloudflare itself has a regional issue, our LB layer is degraded.
The mitigation in production was a Route 53 health-checked record
pointing at the Cloudflare hostname with a fallback target — a "DR for
the DR" so that a Cloudflare outage doesn't black-hole us. That's not
modelled in this repo because the mock router stands in for Cloudflare
and the recursion gets silly.

## We don't model cache warmup

When a region takes over, its in-process and side-car caches are cold.
The first wave of requests after takeover is slower because they all
miss cache. In production, the standby region runs a slow background
prefetch of hot keys, but there's a window of ~2 minutes after takeover
where p99 latency rises sharply. The runbook calls this out
("expect higher latency for ~2 minutes after takeover; do not page on
it") but the design doesn't currently solve it.

## Health checks lie sometimes

The "lying health check" — `/deep` returns 200 but real users see errors —
is the failure mode the design is least equipped for. Our defence is the
canary failback (which exposes lying-health-check regions to a small
fraction of real users before scaling them up), but during initial
failover this still bites. A future iteration would add per-route SLO
probing driven by recent real-traffic error rate, not synthetic checks.

## What we explicitly chose not to build

- **Multi-master writes.** Out of scope. The pain isn't worth it for this
  workload.
- **Strict consistency across regions.** Reads can be slightly stale during
  a primary re-election. Application code accepts this.
- **DR for stateful background jobs.** Cron jobs and long-running batch
  processes run only in the primary region. If the primary is down for
  hours, those jobs run late. Acceptable for our workload.
- **Automatic failback.** Failback is *triggered* by an operator, not
  scheduled. The canary controller automates the *execution* once
  triggered, but a human still says "yes, go." This is intentional —
  failback at 3am during an outage that hasn't been root-caused is a
  great way to cause incident #2.
