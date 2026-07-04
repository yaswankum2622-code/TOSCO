export function shortHash(value: string | undefined, start = 10, end = 8): string {
  if (!value) {
    return "—";
  }

  if (value.length <= start + end + 3) {
    return value;
  }

  return `${value.slice(0, start)}...${value.slice(-end)}`;
}

export function formatMoney(amount: number | undefined, currency = "USD"): string {
  if (typeof amount !== "number" || !Number.isFinite(amount)) {
    return "—";
  }

  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 0
  }).format(amount);
}

export function decisionClass(decision: string | undefined): string {
  switch (decision) {
    case "ALLOW":
      return "decision-allow";
    case "BLOCK":
      return "decision-block";
    case "FREEZE":
      return "decision-freeze";
    case "ESCALATE":
      return "decision-escalate";
    case "REQUEST_MORE_EVIDENCE":
      return "decision-evidence";
    default:
      return "decision-neutral";
  }
}

export function yesNo(value: boolean | undefined): string {
  if (value === true) {
    return "Yes";
  }

  if (value === false) {
    return "No";
  }

  return "—";
}
