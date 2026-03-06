import { useMemo, useState } from "react";
import { runCampaign, type CampaignApiResponse, type CampaignBrief } from "./lib/api";

type VendorStatusItem = {
  label: string;
  status: string;
};

type TransactionItem = {
  label: string;
  amount: number | null;
  status: string;
};

const DEFAULT_VENDORS: VendorStatusItem[] = [
  { label: "🔬 Exa (Research)", status: "Pending" },
  { label: "🌐 Website Guy", status: "Pending" },
  { label: "✍️ Creative Lady", status: "Pending" },
  { label: "📺 ZeroClick (Ads)", status: "Pending" },
];

function toRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function toNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim().length > 0) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return null;
}

function toText(value: unknown, fallback = "—"): string {
  if (typeof value === "string" && value.trim()) {
    return value;
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return String(value);
  }
  return fallback;
}

function formatMoney(amount: number | null): string {
  if (amount === null || !Number.isFinite(amount)) {
    return "—";
  }
  return `$${amount.toFixed(2)}`;
}

export default function App() {
  const [brief, setBrief] = useState<CampaignBrief>({
    brand: "TechStartup X",
    goal: "drive signups",
    audience: "SF tech founders 25-40",
    budget: 15,
  });
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [responseData, setResponseData] = useState<CampaignApiResponse | null>(null);

  const transactions = useMemo<TransactionItem[]>(() => {
    if (!responseData) {
      return [];
    }

    const source = responseData.transactions ?? responseData.payments;
    if (!Array.isArray(source)) {
      return [];
    }

    return source
      .map((entry) => {
        const item = toRecord(entry);
        if (!item) {
          return null;
        }

        return {
          label: toText(item.vendor ?? item.recipient ?? item.type ?? item.description, "Transaction"),
          amount: toNumber(item.amount ?? item.cost ?? item.payment),
          status: toText(item.status ?? item.direction, "Logged"),
        };
      })
      .filter((item): item is TransactionItem => item !== null);
  }, [responseData]);

  const vendorStatuses = useMemo<VendorStatusItem[]>(() => {
    if (!responseData) {
      return DEFAULT_VENDORS;
    }

    const source = responseData.vendor_statuses ?? responseData.vendors;
    if (!Array.isArray(source)) {
      return DEFAULT_VENDORS;
    }

    const rows = source
      .map((entry) => {
        const item = toRecord(entry);
        if (!item) {
          return null;
        }

        return {
          label: toText(item.label ?? item.vendor ?? item.name, "Vendor"),
          status: toText(item.status, "Pending"),
        };
      })
      .filter((item): item is VendorStatusItem => item !== null);

    return rows.length ? rows : DEFAULT_VENDORS;
  }, [responseData]);

  const kpis = useMemo(() => {
    const metrics = toRecord(responseData?.metrics);
    const finance = toRecord(responseData?.finance);

    const spendFromPayload =
      toNumber(responseData?.spend) ??
      toNumber(responseData?.total_spend) ??
      toNumber(responseData?.budget_spent) ??
      toNumber(finance?.spend) ??
      toNumber(finance?.total_spend);

    const spendFromTransactions = transactions.reduce((sum, item) => {
      if (item.amount === null) {
        return sum;
      }
      return sum + Math.max(0, item.amount);
    }, 0);

    const spend = spendFromPayload ?? (transactions.length ? spendFromTransactions : 0);
    const remaining = Math.max(0, brief.budget - spend);

    const roi =
      toText(responseData?.roi, "") ||
      toText(metrics?.roi, "") ||
      (spend > 0 ? `${((brief.budget - spend) / spend).toFixed(2)}x` : "—");

    const marginValue =
      toNumber(responseData?.margin) ??
      toNumber(finance?.margin) ??
      (brief.budget - spend);

    return {
      transactions: toNumber(responseData?.transaction_count) ?? transactions.length,
      spend,
      remaining,
      roi,
      margin: formatMoney(marginValue),
      clicks: toText(responseData?.clicks ?? metrics?.clicks),
      conversions: toText(responseData?.conversions ?? metrics?.conversions),
      switchState: toText(responseData?.switch_state ?? responseData?.switching_action, "HOLD"),
      switchNote: toText(responseData?.switch_note ?? responseData?.recommendation, "Waiting for first campaign run…"),
    };
  }, [brief.budget, responseData, transactions]);

  const strategyOutput = useMemo(() => {
    if (!responseData) {
      return "Run a campaign to populate strategy JSON...";
    }
    const strategy = toRecord(responseData.strategy);
    return JSON.stringify(strategy ?? responseData, null, 2);
  }, [responseData]);

  async function handleRunCampaign() {
    setIsRunning(true);
    setError(null);

    try {
      const result = await runCampaign(brief);
      setResponseData(result);
    } catch (requestError) {
      const message = requestError instanceof Error ? requestError.message : "Failed to run campaign.";
      setError(message);
    } finally {
      setIsRunning(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      <div className="mx-auto max-w-6xl px-6 py-8">
        {/* Header */}
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">AdAgent Studio</h1>
            <p className="text-sm text-gray-600">
              Full-service autonomous marketing agency — internal team + outsourced vendors.
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <span className="rounded-full bg-white px-3 py-1 text-xs shadow-sm ring-1 ring-gray-200">
              Transactions: <span className="font-medium">{kpis.transactions}</span>
            </span>
            <span className="rounded-full bg-white px-3 py-1 text-xs shadow-sm ring-1 ring-gray-200">
              Spend: <span className="font-medium">{formatMoney(kpis.spend)}</span>
            </span>
            <span className="rounded-full bg-white px-3 py-1 text-xs shadow-sm ring-1 ring-gray-200">
              Remaining: <span className="font-medium">{formatMoney(kpis.remaining)}</span>
            </span>
            <span className="rounded-full bg-white px-3 py-1 text-xs shadow-sm ring-1 ring-gray-200">
              ROI: <span className="font-medium">{kpis.roi}</span>
            </span>
            <span className="rounded-full bg-white px-3 py-1 text-xs shadow-sm ring-1 ring-gray-200">
              Margin: <span className="font-medium">{kpis.margin}</span>
            </span>
          </div>
        </div>

        {/* Grid */}
        <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Client Brief */}
          <div className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-200">
            <h2 className="text-sm font-semibold">Client Brief</h2>
            <p className="mt-1 text-xs text-gray-500">
              What the client agent sends your agency.
            </p>

            <div className="mt-4 grid gap-3">
              <label className="grid gap-1 text-xs">
                Brand
                <input
                  className="rounded-xl border border-gray-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-gray-900/10"
                  value={brief.brand}
                  onChange={(e) => setBrief({ ...brief, brand: e.target.value })}
                />
              </label>

              <label className="grid gap-1 text-xs">
                Goal
                <input
                  className="rounded-xl border border-gray-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-gray-900/10"
                  value={brief.goal}
                  onChange={(e) => setBrief({ ...brief, goal: e.target.value })}
                />
              </label>

              <label className="grid gap-1 text-xs">
                Audience
                <input
                  className="rounded-xl border border-gray-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-gray-900/10"
                  value={brief.audience}
                  onChange={(e) => setBrief({ ...brief, audience: e.target.value })}
                />
              </label>

              <label className="grid gap-1 text-xs">
                Budget
                <input
                  type="number"
                  className="rounded-xl border border-gray-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-gray-900/10"
                  value={brief.budget}
                  onChange={(e) => setBrief({ ...brief, budget: Number(e.target.value) })}
                />
              </label>

              <button
                className="mt-2 rounded-2xl bg-gray-900 px-4 py-3 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-70 hover:bg-gray-800"
                onClick={handleRunCampaign}
                disabled={isRunning}
              >
                {isRunning ? "Running Campaign..." : "Run Campaign (CEO Agent)"}
              </button>

              {error && (
                <div className="rounded-xl bg-red-50 px-3 py-2 text-xs text-red-700 ring-1 ring-red-200">
                  {error}
                </div>
              )}

              <div className="rounded-xl bg-gray-50 px-3 py-2 text-xs text-gray-600 ring-1 ring-gray-200">
                Next: this button will call <span className="font-medium">/run-campaign</span> and populate the dashboard.
              </div>
            </div>
          </div>

          {/* Vendor Pipeline */}
          <div className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-200">
            <h2 className="text-sm font-semibold">Vendor Pipeline</h2>
            <p className="mt-1 text-xs text-gray-500">Requested → Paid → Delivered</p>

            <div className="mt-4 space-y-3">
              {vendorStatuses.map((v) => (
                <div key={v.label} className="flex items-center justify-between rounded-2xl bg-gray-50 p-4 ring-1 ring-gray-200">
                  <div className="text-sm font-medium">{v.label}</div>
                  <span className="rounded-full bg-white px-3 py-1 text-xs ring-1 ring-gray-200">
                    ⏳ {v.status}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* ROI Panel */}
          <div className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-200">
            <h2 className="text-sm font-semibold">ROI & Switching</h2>
            <p className="mt-1 text-xs text-gray-500">Shows ROI decisions and vendor/channel switching.</p>

            <div className="mt-4 rounded-2xl bg-gray-50 p-4 ring-1 ring-gray-200">
              <div className="text-xs text-gray-500">ROI</div>
              <div className="mt-1 text-2xl font-semibold">{kpis.roi}</div>

              <div className="mt-4 grid grid-cols-2 gap-3">
                <div className="rounded-xl bg-white p-3 ring-1 ring-gray-200">
                  <div className="text-xs text-gray-500">Clicks</div>
                  <div className="mt-1 text-sm font-medium">{kpis.clicks}</div>
                </div>
                <div className="rounded-xl bg-white p-3 ring-1 ring-gray-200">
                  <div className="text-xs text-gray-500">Conversions</div>
                  <div className="mt-1 text-sm font-medium">{kpis.conversions}</div>
                </div>
              </div>

              <div className="mt-4 rounded-xl bg-white p-3 text-xs ring-1 ring-gray-200">
                <div className="flex items-center justify-between">
                  <div className="font-medium">Switch Logic</div>
                  <span className="rounded-full bg-gray-100 px-3 py-1 text-xs">↔️ {kpis.switchState}</span>
                </div>
                <div className="mt-2 text-gray-600">{kpis.switchNote}</div>
              </div>
            </div>
          </div>
        </div>

        {/* Bottom row */}
        <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Transactions */}
          <div className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-200">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold">Transactions</h2>
              <span className="rounded-full bg-gray-100 px-3 py-1 text-xs">{transactions.length} events</span>
            </div>
            <p className="mt-1 text-xs text-gray-500">
              This will show incoming (client pays) and outgoing (vendors paid).
            </p>

            {transactions.length === 0 ? (
              <div className="mt-4 rounded-2xl bg-gray-50 p-4 text-xs text-gray-600 ring-1 ring-gray-200">
                Run a campaign to see live transactions here.
              </div>
            ) : (
              <div className="mt-4 space-y-2">
                {transactions.map((item, index) => (
                  <div
                    key={`${item.label}-${index}`}
                    className="flex items-center justify-between rounded-xl bg-gray-50 px-3 py-2 text-xs ring-1 ring-gray-200"
                  >
                    <span className="font-medium text-gray-700">{item.label}</span>
                    <span className="text-gray-600">{formatMoney(item.amount)} · {item.status}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Strategy JSON */}
          <div className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-200">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold">Strategy Output</h2>
              <span className="rounded-full bg-gray-100 px-3 py-1 text-xs">CEO → Strategy Agent</span>
            </div>
            <p className="mt-1 text-xs text-gray-500">
              Strategy doc drives outsourcing + budget split.
            </p>

            <pre className="mt-4 max-h-64 overflow-auto rounded-2xl bg-gray-50 p-4 text-xs text-gray-700 ring-1 ring-gray-200">
{strategyOutput}
            </pre>
          </div>
        </div>

        <div className="mt-8 text-xs text-gray-500">
          Next step: connect the Run button to backend and populate these panels with real data.
        </div>
      </div>
    </div>
  );
}