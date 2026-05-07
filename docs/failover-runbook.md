# Failover runbook

This is the runbook the on-call engineer follows when the system fails over
or needs to be failed over manually.

## Detection

You'll hear about it from one of three places, roughly in this order:

1. **PagerDuty** — fired by the Cloudflare LB pool-down notification.
2. **Slack `#alerts`** — posted by the synthetic checker that runs every 30s
   from a third location.
3. **Customer reports** — by the time these arrive, the automated layer
   should already be cutting over. If they don't, jump to "Manual cutover".

## Automatic failover (the happy path)

When the primary pool goes unhealthy for two consecutive probes, Cloudflare
removes it from rotation. No human action needed. Your job is to:

1. Confirm in the Cloudflare LB dashboard that the primary pool is `Critical`
   and traffic is flowing to the standby pool.
2. Open the regional dashboard for the *failed* region and start the RCA.
3. Acknowledge the page. Do **not** start failback yet.
4. Post a status update in `#incidents`.

## Manual cutover

You'll need this when health probes report green but customers see errors —
classic "lying health check" scenario.

```bash
# 1. Force the bad pool out of rotation
curl -X PATCH https://api.cloudflare.com/client/v4/accounts/$CF_ACC/load_balancers/pools/$POOL_ID \
  -H "Authorization: Bearer $CF_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'

# 2. Verify traffic moved
curl -s https://api.example.com/health/deep | jq '.region'
# expected: "aws-singapore"

# 3. Page the regional engineer for RCA
```

## Failback (the dangerous part)

**Do not flip 100% of traffic back.** Use the canary controller.

Preconditions before starting failback:

- [ ] The original failure mode is understood and fixed
- [ ] All deep-health checks against the recovered region have been green
      for ≥ 10 minutes
- [ ] Mongo Atlas shows the recovered region's app pods reading from the
      nearest secondary cleanly (check Atlas Performance Advisor)
- [ ] You have ≥ 60 minutes of focus and an eye on the dashboards

Then run the canary:

```bash
# Start the ramp
curl -X POST $ROUTER/admin/canary/start \
  -H 'content-type: application/json' \
  -d '{"target":"aws-mumbai"}'

# Watch it
watch -n 5 'curl -s $ROUTER/admin/canary/status | jq'
```

The ramp is **5% → 25% → 50% → 100%** with hold windows. Total runtime
~8 minutes when nothing goes wrong. The controller monitors the recovered
region throughout; if it transitions away from HEALTHY during any hold
window, weight is set back to 0 and the run exits in `rolled_back` state.
You'll see this in the canary status payload.

If it rolls back: do not re-start the canary. Treat the rollback as a
second incident. Investigate first.

## After it's over

1. File the incident report (template in `docs/incident-template.md`).
2. Update this runbook if the playbook didn't match reality.
3. If the failover added > 90s of user-visible 5xx, add a ticket to look at
   probe interval and unhealthy threshold — that's RTO drift.

## What not to do

- **Don't restart Cloudflare changes from another engineer's session.**
  Cloudflare's API doesn't have transactional locking on pool changes;
  two engineers fighting will lose updates.
- **Don't bypass the canary** even on "small" failbacks. The ramp exists
  precisely because the small ones are the ones that bite.
- **Don't truncate the hold windows** to "save time." The hold windows
  are the test. If you cut them, you've removed the safety from the
  failback procedure.
