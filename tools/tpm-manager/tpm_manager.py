"""
TPM (Tokens Per Minute) Manager for Azure AI Foundry Model Deployments.

Check, adjust, and estimate TPM requirements for Content Understanding video processing.

Usage:
    # Check current TPM for a deployment
    python tpm_manager.py check --deployment gpt-5.2

    # Set TPM to a specific value (in thousands)
    python tpm_manager.py set --deployment gpt-5.2 --tpm 2000

    # Set TPM to maximum available quota
    python tpm_manager.py max --deployment gpt-5.2

    # Estimate TPM needed for a workload
    python tpm_manager.py estimate --parallel 5 --video-hours 1.0

    # Check if current TPM is sufficient for a workload
    python tpm_manager.py check-sufficient --deployment gpt-5.2 --parallel 5 --video-hours 1.0
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path


# Default resource configuration (can be overridden via env or args)
DEFAULT_RESOURCE = "mmi-usw3-eft-foundry"
DEFAULT_RESOURCE_GROUP = "mmi-usw3-eft"
DEFAULT_LOCATION = "westus3"

# Token usage constants derived from empirical testing (GPT-5.2, ~1hr video)
# From 5x test: avg 1,274,512 input + 35,993 output = 1,310,505 total per run
TOKENS_PER_VIDEO_HOUR_INPUT = 1_305_000   # ~1.3M input tokens per video-hour
TOKENS_PER_VIDEO_HOUR_OUTPUT = 37_000      # ~37K output tokens per video-hour
TOKENS_PER_VIDEO_HOUR_TOTAL = 1_342_000    # ~1.34M total tokens per video-hour

# Processing time observations (minutes)
SINGLE_RUN_LATENCY_MIN_GPT52 = 46   # Single GPT-5.2 run, adequate TPM
SINGLE_RUN_LATENCY_MIN_GPT41 = 32   # Single GPT-4.1 run, adequate TPM


def run_az(args_list, parse_json=True):
    """Run an az CLI command and return parsed output."""
    cmd = ["az"] + args_list + ["-o", "json"]
    result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    if result.returncode != 0:
        print(f"ERROR: az command failed: {' '.join(cmd)}", file=sys.stderr)
        print(f"  {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    if parse_json and result.stdout.strip():
        return json.loads(result.stdout)
    return result.stdout


def get_deployment(resource, rg, deployment_name):
    """Get deployment details."""
    return run_az([
        "cognitiveservices", "account", "deployment", "show",
        "--name", resource,
        "--resource-group", rg,
        "--deployment-name", deployment_name
    ])


def get_quota(location, model_name):
    """Get quota usage for a model."""
    usages = run_az(["cognitiveservices", "usage", "list", "--location", location])
    for item in usages:
        name = item.get("name", {}).get("value", "")
        if model_name in name and "GlobalStandard" in name:
            return {
                "name": name,
                "current": item.get("currentValue", 0),
                "limit": item.get("limit", 0),
                "unit": "thousands of TPM"
            }
    return None


def set_deployment_capacity(resource, rg, deployment_name, capacity_k):
    """Set deployment capacity (in thousands of TPM)."""
    # Get current deployment to preserve model info
    dep = get_deployment(resource, rg, deployment_name)
    model = dep['properties']['model']
    return run_az([
        "cognitiveservices", "account", "deployment", "create",
        "--name", resource,
        "--resource-group", rg,
        "--deployment-name", deployment_name,
        "--model-name", model['name'],
        "--model-version", model['version'],
        "--model-format", model.get('format', 'OpenAI'),
        "--sku-name", "GlobalStandard",
        "--sku-capacity", str(int(capacity_k))
    ], parse_json=False)


def cmd_check(args):
    """Check current TPM for a deployment."""
    dep = get_deployment(args.resource, args.resource_group, args.deployment)
    sku = dep.get("sku", {})
    capacity_k = sku.get("capacity", 0)
    rate_limits = dep.get("properties", {}).get("rateLimits", [])

    print(f"═══════════════════════════════════════════════")
    print(f"  Deployment: {args.deployment}")
    print(f"  Model: {dep['properties']['model']['name']} (v{dep['properties']['model']['version']})")
    print(f"  SKU: {sku.get('name')} (capacity: {capacity_k}K)")
    print(f"═══════════════════════════════════════════════")
    print(f"  TPM (Tokens/min):  {capacity_k * 1000:>12,}")
    for rl in rate_limits:
        key = rl.get("key", "")
        count = rl.get("count", 0)
        print(f"  {key:>16}: {count:>12,.0f}")
    print()

    # Also show quota
    quota = get_quota(args.location, dep['properties']['model']['name'])
    if quota:
        available = quota["limit"] - quota["current"]
        print(f"  Quota: {quota['current']:.0f}K / {quota['limit']:.0f}K used")
        print(f"  Available to add: {available:.0f}K ({available * 1000:,.0f} TPM)")
        print(f"  Max this deployment could be: {capacity_k + available:.0f}K ({(capacity_k + available) * 1000:,.0f} TPM)")

    return capacity_k


def cmd_set(args):
    """Set TPM to a specific value."""
    dep = get_deployment(args.resource, args.resource_group, args.deployment)
    current_k = dep.get("sku", {}).get("capacity", 0)
    target_k = args.tpm

    quota = get_quota(args.location, dep['properties']['model']['name'])
    if quota:
        other_usage = quota["current"] - current_k
        max_for_this = quota["limit"] - other_usage
        if target_k > max_for_this:
            print(f"ERROR: Requested {target_k}K exceeds available quota ({max_for_this:.0f}K)")
            print(f"  Total quota: {quota['limit']:.0f}K, other deployments using: {other_usage:.0f}K")
            sys.exit(1)

    print(f"Setting {args.deployment} TPM: {current_k}K → {target_k}K ({target_k * 1000:,} tokens/min)")
    set_deployment_capacity(args.resource, args.resource_group, args.deployment, target_k)
    print(f"✅ Done. New TPM: {target_k * 1000:,}")


def cmd_max(args):
    """Set TPM to maximum available quota."""
    dep = get_deployment(args.resource, args.resource_group, args.deployment)
    current_k = dep.get("sku", {}).get("capacity", 0)
    model_name = dep['properties']['model']['name']

    quota = get_quota(args.location, model_name)
    if not quota:
        print(f"ERROR: Could not find quota for {model_name}")
        sys.exit(1)

    other_usage = quota["current"] - current_k
    max_k = quota["limit"] - other_usage
    
    if max_k <= current_k:
        print(f"Already at max capacity ({current_k}K). Quota limit: {quota['limit']:.0f}K")
        return

    print(f"Setting {args.deployment} to MAX: {current_k}K → {max_k:.0f}K ({max_k * 1000:,.0f} tokens/min)")
    print(f"  (Quota: {quota['limit']:.0f}K total, {other_usage:.0f}K used by other deployments)")
    set_deployment_capacity(args.resource, args.resource_group, args.deployment, int(max_k))
    print(f"✅ Done. New TPM: {int(max_k) * 1000:,}")


def cmd_estimate(args):
    """Estimate TPM needed for a video processing workload."""
    parallel = args.parallel
    video_hours = args.video_hours
    target_latency_min = args.target_latency or SINGLE_RUN_LATENCY_MIN_GPT52

    # Each parallel job consumes tokens over the processing window
    tokens_per_job = int(TOKENS_PER_VIDEO_HOUR_TOTAL * video_hours)
    total_tokens = tokens_per_job * parallel

    # TPM needed = total tokens consumed across all parallel jobs / target latency in minutes
    # This assumes tokens are consumed roughly evenly across the processing window
    tpm_needed = total_tokens / target_latency_min

    # Add 20% headroom for bursts
    tpm_with_headroom = tpm_needed * 1.2
    tpm_k = int(tpm_with_headroom / 1000) + 1

    print(f"═══════════════════════════════════════════════")
    print(f"  TPM ESTIMATE — Video Processing Workload")
    print(f"═══════════════════════════════════════════════")
    print(f"  Parallel jobs:     {parallel}")
    print(f"  Video length:      {video_hours:.2f} hours each")
    print(f"  Target latency:    {target_latency_min} min per job")
    print(f"  Model:             GPT-5.2")
    print(f"───────────────────────────────────────────────")
    print(f"  Tokens per job:    {tokens_per_job:>12,}")
    print(f"    Input:           {int(TOKENS_PER_VIDEO_HOUR_INPUT * video_hours):>12,}")
    print(f"    Output:          {int(TOKENS_PER_VIDEO_HOUR_OUTPUT * video_hours):>12,}")
    print(f"  Total tokens:      {total_tokens:>12,} (all {parallel} jobs)")
    print(f"───────────────────────────────────────────────")
    print(f"  TPM needed:        {int(tpm_needed):>12,}")
    print(f"  TPM w/ headroom:   {int(tpm_with_headroom):>12,} (+20%)")
    print(f"  Recommended:       {tpm_k}K ({tpm_k * 1000:,} TPM)")
    print()

    # Production scenario
    if args.interval:
        jobs_per_hour = 60 / args.interval
        print(f"  Production scenario: 1 video every {args.interval} min")
        print(f"    Max concurrent (overlap): {int(target_latency_min / args.interval) + 1} jobs")
        concurrent = int(target_latency_min / args.interval) + 1
        prod_tpm = int(TOKENS_PER_VIDEO_HOUR_TOTAL * video_hours * concurrent / target_latency_min * 1.2)
        prod_tpm_k = prod_tpm // 1000 + 1
        print(f"    Recommended TPM:  {prod_tpm_k}K ({prod_tpm_k * 1000:,} TPM)")


def cmd_check_sufficient(args):
    """Check if current TPM is sufficient for a workload. Returns exit code 0 if OK, 1 if not."""
    dep = get_deployment(args.resource, args.resource_group, args.deployment)
    current_k = dep.get("sku", {}).get("capacity", 0)
    current_tpm = current_k * 1000

    parallel = args.parallel
    video_hours = args.video_hours
    target_latency = args.target_latency or SINGLE_RUN_LATENCY_MIN_GPT52

    tokens_per_job = int(TOKENS_PER_VIDEO_HOUR_TOTAL * video_hours)
    total_tokens = tokens_per_job * parallel
    tpm_needed = total_tokens / target_latency
    tpm_with_headroom = tpm_needed * 1.2

    sufficient = current_tpm >= tpm_with_headroom

    print(f"TPM Check: {args.deployment}")
    print(f"  Current TPM:    {current_tpm:>10,}")
    print(f"  Needed TPM:     {int(tpm_with_headroom):>10,} ({parallel} parallel × {video_hours:.1f}hr video)")
    
    if sufficient:
        ratio = current_tpm / tpm_with_headroom
        print(f"  ✅ SUFFICIENT ({ratio:.1f}x headroom)")
    else:
        deficit = int(tpm_with_headroom - current_tpm)
        print(f"  ⚠️  INSUFFICIENT — need {deficit:,} more TPM")
        print(f"  Recommendation: Set to at least {int(tpm_with_headroom / 1000) + 1}K")
        print(f"  Run: python tpm_manager.py set --deployment {args.deployment} --tpm {int(tpm_with_headroom / 1000) + 1}")

    return 0 if sufficient else 1


def main():
    parser = argparse.ArgumentParser(description="TPM Manager for Azure AI Model Deployments")
    parser.add_argument("--resource", default=DEFAULT_RESOURCE, help="Cognitive Services account name")
    parser.add_argument("--resource-group", default=DEFAULT_RESOURCE_GROUP, help="Resource group")
    parser.add_argument("--location", default=DEFAULT_LOCATION, help="Azure region")

    sub = parser.add_subparsers(dest="command", required=True)

    # check
    p_check = sub.add_parser("check", help="Check current TPM")
    p_check.add_argument("--deployment", required=True, help="Deployment name")

    # set
    p_set = sub.add_parser("set", help="Set TPM (in thousands)")
    p_set.add_argument("--deployment", required=True)
    p_set.add_argument("--tpm", type=int, required=True, help="TPM in thousands (e.g., 2000 = 2M TPM)")

    # max
    p_max = sub.add_parser("max", help="Set TPM to maximum available quota")
    p_max.add_argument("--deployment", required=True)

    # estimate
    p_est = sub.add_parser("estimate", help="Estimate TPM needed for workload")
    p_est.add_argument("--parallel", type=int, default=1, help="Number of parallel jobs")
    p_est.add_argument("--video-hours", type=float, default=1.0, help="Video length in hours")
    p_est.add_argument("--target-latency", type=int, help="Target per-job latency in minutes")
    p_est.add_argument("--interval", type=int, help="Production interval: new video every N minutes")

    # check-sufficient
    p_suf = sub.add_parser("check-sufficient", help="Check if TPM is sufficient for workload")
    p_suf.add_argument("--deployment", required=True)
    p_suf.add_argument("--parallel", type=int, default=1)
    p_suf.add_argument("--video-hours", type=float, default=1.0)
    p_suf.add_argument("--target-latency", type=int, help="Target latency in minutes")

    args = parser.parse_args()

    if args.command == "check":
        cmd_check(args)
    elif args.command == "set":
        cmd_set(args)
    elif args.command == "max":
        cmd_max(args)
    elif args.command == "estimate":
        cmd_estimate(args)
    elif args.command == "check-sufficient":
        exit_code = cmd_check_sufficient(args)
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
