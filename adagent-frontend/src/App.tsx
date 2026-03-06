import { useMemo, useState } from "react";
import { runMindraCampaign, type CampaignApiResponse, type CampaignBrief } from "./lib/api";
import {
  marketplaceReadiness,
  monetizationGuidance,
  neverminedJourney,
  paymentRails,
  resourceLinks,
} from "./content/nevermindGuide";

type VendorStatusItem = {
  label: string;
  status: string;
};

type TransactionItem = {
  label: string;
  amount: number | null;
  status: string;
};

type TreeNodeItem = {
  id: string;
  name: string;
  depth: number;
  status: string;
  prompt: string;
  children: string[];
};

type WebsiteAgentOutput = {
  nodeId: string;
  name: string;
  status: string;
  output: unknown;
};

type MindraContentOutput = {
  nodeId: string;
  name: string;
  status: string;
  output: unknown;
};

function cleanNodeLabel(value: string): string {
  return value.replace(/mindra\s*/gi, "").trim();
}

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

function statusTone(status: string): string {
  const s = status.toLowerCase();
  if (s === "done" || s === "paid" || s === "complete") {
    return "bg-emerald-50 text-emerald-700 ring-emerald-200";
  }
  if (s === "running") {
    return "bg-amber-50 text-amber-700 ring-amber-200";
  }
  if (s === "skipped" || s === "not required") {
    return "bg-slate-100 text-slate-700 ring-slate-200";
  }
  if (s === "failed" || s === "error" || s === "insufficient budget") {
    return "bg-rose-50 text-rose-700 ring-rose-200";
  }
  return "bg-white text-gray-700 ring-gray-200";
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

  const mindraTree = useMemo<TreeNodeItem[]>(() => {
    const mindra = toRecord(responseData?.mindra);
    const source = mindra?.tree;
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
          id: toText(item.id, "node"),
          name: toText(item.name, "Node"),
          depth: toNumber(item.depth) ?? 0,
          status: toText(item.status, "pending"),
          prompt: toText(item.prompt ?? item.task, "No prompt available."),
          children: Array.isArray(item.children)
            ? item.children.map((child) => toText(child, "")).filter((child) => child.length > 0)
            : [],
        };
      })
      .filter((item): item is TreeNodeItem => item !== null);
  }, [responseData]);

  const websiteAgentOutput = useMemo<WebsiteAgentOutput | null>(() => {
    const agents = toRecord(responseData?.agents);
    if (!agents) {
      return null;
    }

    for (const [nodeId, rawNode] of Object.entries(agents)) {
      const node = toRecord(rawNode);
      if (!node) {
        continue;
      }

      const name = toText(node.name, "");
      const low = `${nodeId} ${name}`.toLowerCase();
      if (!low.includes("website")) {
        continue;
      }

      return {
        nodeId,
        name: name || "Website Agent",
        status: toText(node.status, "unknown"),
        output: node.output,
      };
    }

    return null;
  }, [responseData]);

  const mindraContentOutput = useMemo<MindraContentOutput | null>(() => {
    const agents = toRecord(responseData?.agents);
    if (!agents) {
      return null;
    }

    for (const [nodeId, rawNode] of Object.entries(agents)) {
      const node = toRecord(rawNode);
      if (!node) {
        continue;
      }

      const name = toText(node.name, "");
      const out = toRecord(node.output);
      const provider = toText(out?.provider, "").toLowerCase();
      const low = `${nodeId} ${name}`.toLowerCase();
      const isMindraContent = (low.includes("mindra") && low.includes("content")) || provider === "mindra";
      if (!isMindraContent) {
        continue;
      }

      return {
        nodeId,
        name: cleanNodeLabel(name || "Content Creator Agent"),
        status: toText(node.status, "unknown"),
        output: node.output,
      };
    }

    return null;
  }, [responseData]);

  function openDiagramTab() {
    if (!mindraTree.length) {
      return;
    }

    const esc = (value: string) =>
      value
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");

    const byId = new Map(mindraTree.map((node) => [node.id, node]));
    const hasParent = new Set<string>();
    mindraTree.forEach((node) => {
      node.children.forEach((childId) => {
        if (byId.has(childId)) {
          hasParent.add(childId);
        }
      });
    });

    const roots = mindraTree.filter((node) => !hasParent.has(node.id));
    const layerById = new Map<string, number>();
    const queue: string[] = [];

    roots.forEach((node) => {
      layerById.set(node.id, 0);
      queue.push(node.id);
    });

    while (queue.length > 0) {
      const currentId = queue.shift()!;
      const current = byId.get(currentId);
      if (!current) {
        continue;
      }

      const currentLayer = layerById.get(currentId) ?? 0;
      current.children.forEach((childId) => {
        if (!byId.has(childId)) {
          return;
        }
        const nextLayer = currentLayer + 1;
        const prevLayer = layerById.get(childId);
        if (prevLayer === undefined || nextLayer > prevLayer) {
          layerById.set(childId, nextLayer);
          queue.push(childId);
        }
      });
    }

    // Any disconnected nodes are shown at root level.
    mindraTree.forEach((node) => {
      if (!layerById.has(node.id)) {
        layerById.set(node.id, 0);
      }
    });

    const nodesByLayer = new Map<number, TreeNodeItem[]>();
    mindraTree.forEach((node) => {
      const layer = layerById.get(node.id) ?? 0;
      const bucket = nodesByLayer.get(layer) ?? [];
      bucket.push(node);
      nodesByLayer.set(layer, bucket);
    });

    const sortedLayers = Array.from(nodesByLayer.keys()).sort((a, b) => a - b);
    sortedLayers.forEach((layer) => {
      const items = nodesByLayer.get(layer) ?? [];
      items.sort((a, b) => a.name.localeCompare(b.name));
    });

    const nodeWidth = 180;
    const levelYGap = 130;
    const nodeXGap = 220;
    const maxPerLayer = Math.max(1, ...Array.from(nodesByLayer.values()).map((arr) => arr.length));
    const maxLayer = Math.max(0, ...sortedLayers);
    const width = Math.max(1000, 140 + maxPerLayer * nodeXGap);
    const height = Math.max(700, 180 + (maxLayer + 1) * levelYGap);

    const positioned: Array<TreeNodeItem & { x: number; y: number; layer: number }> = [];
    const posById = new Map<string, { x: number; y: number; layer: number }>();

    sortedLayers.forEach((layer) => {
      const layerNodes = nodesByLayer.get(layer) ?? [];
      const groupWidth = (layerNodes.length - 1) * nodeXGap;
      const startX = width / 2 - groupWidth / 2;
      const y = 100 + layer * levelYGap;

      layerNodes.forEach((node, index) => {
        const x = startX + index * nodeXGap;
        const p = { ...node, x, y, layer };
        positioned.push(p);
        posById.set(node.id, { x, y, layer });
      });
    });

    const lines = positioned
      .flatMap((node) =>
        node.children.map((childId) => {
          const childPos = posById.get(childId);
          if (!childPos) {
            return "";
          }
          return `<line x1="${node.x}" y1="${node.y + 28}" x2="${childPos.x}" y2="${childPos.y - 28}" stroke="#9ca3af" stroke-width="2" />`;
        })
      )
      .join("\n");

    const nodes = positioned
      .map((node) => {
        const fill =
          node.status.toLowerCase() === "done"
            ? "#dcfce7"
            : node.status.toLowerCase() === "running"
              ? "#fef3c7"
              : node.status.toLowerCase() === "skipped"
                ? "#f3f4f6"
                : "#e5e7eb";

        return `
          <g>
            <title>${esc(node.name)}\nPrompt: ${esc(node.prompt)}\nStatus: ${esc(node.status)}</title>
            <rect x="${node.x - 90}" y="${node.y - 28}" rx="12" ry="12" width="${nodeWidth}" height="56" fill="${fill}" stroke="#6b7280" />
            <text x="${node.x}" y="${node.y - 4}" text-anchor="middle" font-size="13" fill="#111827" font-family="Arial">${esc(node.name)}</text>
            <text x="${node.x}" y="${node.y + 14}" text-anchor="middle" font-size="11" fill="#4b5563" font-family="Arial">${esc(node.status)}</text>
          </g>
        `;
      })
      .join("\n");

    const html = `
      <!doctype html>
      <html>
        <head>
          <meta charset="utf-8" />
          <title>Execution Graph Diagram</title>
          <style>
            body { margin: 0; font-family: Arial, sans-serif; background: #f8fafc; }
            .header { padding: 14px 18px; border-bottom: 1px solid #e5e7eb; background: #ffffff; }
            .title { font-size: 16px; font-weight: 600; color: #111827; }
            .subtitle { margin-top: 4px; font-size: 12px; color: #6b7280; }
            .wrap { padding: 12px; overflow: auto; }
            svg { background: #ffffff; border: 1px solid #e5e7eb; border-radius: 12px; }
          </style>
        </head>
        <body>
          <div class="header">
            <div class="title">Agent Execution Graph</div>
            <div class="subtitle">Hover any node to see its prompt/task. Source: ${esc(toText(responseData?.campaign_id, "local-run"))}</div>
          </div>
          <div class="wrap">
            <svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
              ${lines}
              ${nodes}
            </svg>
          </div>
        </body>
      </html>
    `;

    const blob = new Blob([html], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    const tab = window.open(url, "_blank");
    if (!tab) {
      URL.revokeObjectURL(url);
      setError("Popup blocked. Please allow popups and try again.");
      return;
    }

    // Keep URL alive briefly so the new tab can fully load it.
    window.setTimeout(() => URL.revokeObjectURL(url), 60000);
  }

  function openWebsiteOutputTab() {
    if (!websiteAgentOutput) {
      setError("No Website Agent output available yet.");
      return;
    }

    const esc = (value: string) =>
      value
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\"/g, "&quot;")
        .replace(/'/g, "&#39;");

    const out = toRecord(websiteAgentOutput.output);
    const landingPageUrl = toText(out?.landing_page_url ?? out?.url ?? out?.landingUrl, "");
    const sections = Array.isArray(out?.sections) ? out?.sections : [];

    const sectionRows = sections
      .map((s) => {
        if (typeof s === "string") {
          return `<li>${esc(s)}</li>`;
        }
        const obj = toRecord(s);
        if (!obj) {
          return "";
        }
        const title = esc(toText(obj.title ?? obj.heading ?? obj.name, "Section"));
        const body = esc(toText(obj.content ?? obj.body ?? obj.description, ""));
        return `<li><strong>${title}</strong>${body ? `<div style=\"margin-top:4px;color:#4b5563\">${body}</div>` : ""}</li>`;
      })
      .join("\n");

    const outputJson = esc(JSON.stringify(websiteAgentOutput.output ?? {}, null, 2));

    const html = `
      <!doctype html>
      <html>
        <head>
          <meta charset="utf-8" />
          <title>Website Agent Output</title>
          <style>
            body { margin: 0; font-family: Arial, sans-serif; background: #f8fafc; color: #111827; }
            .header { padding: 14px 18px; border-bottom: 1px solid #e5e7eb; background: #ffffff; }
            .title { font-size: 16px; font-weight: 600; }
            .meta { margin-top: 4px; font-size: 12px; color: #6b7280; }
            .wrap { padding: 16px; display: grid; gap: 14px; }
            .card { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 14px; }
            .label { font-size: 12px; color: #6b7280; margin-bottom: 8px; }
            a { color: #2563eb; text-decoration: none; }
            a:hover { text-decoration: underline; }
            pre { margin: 0; white-space: pre-wrap; word-break: break-word; font-size: 12px; color: #374151; }
            ul { margin: 0; padding-left: 18px; }
            li { margin: 8px 0; }
            iframe { width: 100%; min-height: 420px; border: 1px solid #e5e7eb; border-radius: 10px; }
          </style>
        </head>
        <body>
          <div class="header">
            <div class="title">Website Agent Output</div>
            <div class="meta">Node: ${esc(websiteAgentOutput.name)} (${esc(websiteAgentOutput.nodeId)}) · Status: ${esc(websiteAgentOutput.status)}</div>
          </div>
          <div class="wrap">
            <div class="card">
              <div class="label">Landing Page URL</div>
              ${landingPageUrl ? `<a href="${esc(landingPageUrl)}" target="_blank" rel="noreferrer">${esc(landingPageUrl)}</a>` : "<div>No landing_page_url returned by agent.</div>"}
            </div>
            ${sectionRows ? `<div class="card"><div class="label">Sections</div><ul>${sectionRows}</ul></div>` : ""}
            ${landingPageUrl ? `<div class="card"><div class="label">Live Preview (if embeddable)</div><iframe src="${esc(landingPageUrl)}"></iframe></div>` : ""}
            <div class="card">
              <div class="label">Raw Output JSON</div>
              <pre>${outputJson}</pre>
            </div>
          </div>
        </body>
      </html>
    `;

    const blob = new Blob([html], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    const tab = window.open(url, "_blank");
    if (!tab) {
      URL.revokeObjectURL(url);
      setError("Popup blocked. Please allow popups and try again.");
      return;
    }
    window.setTimeout(() => URL.revokeObjectURL(url), 60000);
  }

  function openMindraContentTab() {
    if (!mindraContentOutput) {
      setError("No content creator output available yet.");
      return;
    }

    const esc = (value: string) =>
      value
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\"/g, "&quot;")
        .replace(/'/g, "&#39;");

    const out = toRecord(mindraContentOutput.output);
    const creatives = Array.isArray(out?.creatives) ? out?.creatives : [];

    const normalizeBody = (raw: string) => {
      let text = raw || "";
      const anchor = "Here are **3 ad creative variants";
      const anchorIndex = text.indexOf(anchor);
      if (anchorIndex >= 0) {
        text = text.slice(anchorIndex);
      }

      // Drop obvious JSON event envelopes that can leak into the body string.
      text = text
        .split("\n")
        .filter((line) => {
          const trimmed = line.trim();
          return !(trimmed.startsWith('{"event_id"') || trimmed.startsWith('{"event_type"'));
        })
        .join("\n");

      return text.trim();
    };

    const splitVariantBody = (body: string) => {
      const normalized = normalizeBody(body);
      if (!normalized) {
        return [] as Array<{ title: string; body: string }>;
      }

      const withMarker = `\n${normalized}`;
      const parts = withMarker.split(/\n##\s+/g).map((p) => p.trim()).filter(Boolean);
      if (parts.length < 2) {
        return [{ title: "Variant", body: normalized }];
      }

      const variants: Array<{ title: string; body: string }> = [];
      for (const part of parts) {
        const lines = part.split("\n");
        const title = lines[0]?.trim() || "Variant";
        const bodyText = lines.slice(1).join("\n").trim();
        if (bodyText) {
          variants.push({ title, body: bodyText });
        }
      }
      return variants;
    };

    const expandedCreatives = creatives.flatMap((c, idx) => {
      const item = toRecord(c);
      if (!item) {
        return [] as Array<Record<string, unknown>>;
      }
      const body = toText(item.body, "");
      const split = splitVariantBody(body);
      if (split.length <= 1) {
        return [{
          ...item,
          headline: toText(item.headline, `Variant ${idx + 1}`),
          body: normalizeBody(body),
        }];
      }
      return split.slice(0, 3).map((variant, vIdx) => ({
        headline: variant.title || `Variant ${vIdx + 1}`,
        body: variant.body,
        cta: toText(item.cta, "Use this copy"),
        format: toText(item.format, "text"),
      }));
    });

    const visibleCreatives = expandedCreatives.slice(0, 3);

    const creativeRows = visibleCreatives
      .map((c, index) => {
        const item = toRecord(c);
        if (!item) {
          return "";
        }
        const headline = esc(toText(item.headline, `Variant ${index + 1}`));
        const body = esc(toText(item.body, "")).replace(/\n/g, "<br />");
        const cta = esc(toText(item.cta, ""));
        const format = esc(toText(item.format, ""));
        return `
          <article class="variant-card">
            <div class="variant-kicker">Campaign Angle ${index + 1}</div>
            ${headline ? `<h2>${headline}</h2>` : ""}
            ${body ? `<div class="variant-body">${body}</div>` : ""}
            <div class="variant-footer">
              ${cta ? `<span><strong>CTA:</strong> ${cta}</span>` : ""}
              ${format ? `<span class="pill">${format}</span>` : ""}
            </div>
          </article>
        `;
      })
      .join("\n");

    const html = `
      <!doctype html>
      <html>
        <head>
          <meta charset="utf-8" />
          <title>Content Creator Output</title>
          <style>
            :root {
              --bg: #f7f4ef;
              --surface: #fffdf8;
              --ink: #1d252d;
              --muted: #5c6773;
              --line: #e8ddd0;
              --accent: #b45f34;
              --accent-soft: #f6e5d8;
            }
            * { box-sizing: border-box; }
            body {
              margin: 0;
              font-family: Georgia, "Times New Roman", serif;
              background: radial-gradient(circle at top right, #f9efe5, var(--bg) 42%);
              color: var(--ink);
            }
            .site-header {
              border-bottom: 1px solid var(--line);
              background: rgba(255, 253, 248, 0.92);
              backdrop-filter: blur(4px);
              position: sticky;
              top: 0;
              z-index: 10;
            }
            .header-inner {
              max-width: 1080px;
              margin: 0 auto;
              padding: 14px 20px;
              display: flex;
              align-items: center;
              justify-content: space-between;
              gap: 14px;
            }
            .brand {
              font-size: 22px;
              letter-spacing: 0.02em;
              font-weight: 700;
            }
            .brand-dot {
              color: var(--accent);
            }
            .nav {
              display: flex;
              gap: 14px;
              font-size: 13px;
              color: var(--muted);
            }
            .hero {
              max-width: 1080px;
              margin: 0 auto;
              padding: 56px 20px 24px;
            }
            .hero-kicker {
              font-size: 12px;
              letter-spacing: 0.16em;
              text-transform: uppercase;
              color: var(--accent);
            }
            .hero h1 {
              margin: 14px 0 12px;
              font-size: clamp(28px, 5vw, 52px);
              line-height: 1.08;
              max-width: 14ch;
            }
            .hero p {
              margin: 0;
              color: var(--muted);
              max-width: 62ch;
              font-size: 18px;
              line-height: 1.45;
            }
            .content {
              max-width: 1080px;
              margin: 0 auto;
              padding: 14px 20px 56px;
            }
            .variant-grid {
              display: grid;
              grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
              gap: 16px;
            }
            .variant-card {
              background: var(--surface);
              border: 1px solid var(--line);
              border-radius: 16px;
              padding: 18px;
              box-shadow: 0 10px 30px rgba(31, 17, 3, 0.06);
              display: flex;
              flex-direction: column;
            }
            .variant-kicker {
              font-size: 11px;
              text-transform: uppercase;
              letter-spacing: 0.12em;
              color: var(--muted);
            }
            .variant-card h2 {
              margin: 10px 0 0;
              font-size: 28px;
              line-height: 1.2;
            }
            .variant-body {
              margin-top: 14px;
              color: #26313d;
              line-height: 1.65;
              font-size: 17px;
              flex: 1;
            }
            .variant-footer {
              margin-top: 16px;
              padding-top: 12px;
              border-top: 1px dashed var(--line);
              display: flex;
              align-items: center;
              justify-content: space-between;
              gap: 8px;
              font-size: 13px;
              color: var(--muted);
            }
            .pill {
              background: var(--accent-soft);
              color: #7f3d1e;
              border-radius: 999px;
              padding: 5px 10px;
              text-transform: capitalize;
              font-size: 12px;
            }
            .empty {
              border: 1px dashed var(--line);
              border-radius: 14px;
              padding: 20px;
              color: var(--muted);
              background: var(--surface);
            }
            @media (max-width: 700px) {
              .header-inner { padding: 12px 14px; }
              .nav { display: none; }
              .hero { padding: 36px 14px 20px; }
              .content { padding: 10px 14px 44px; }
              .variant-card h2 { font-size: 22px; }
              .variant-body { font-size: 16px; }
            }
          </style>
        </head>
        <body>
          <header class="site-header">
            <div class="header-inner">
              <div class="brand">TechStartup X<span class="brand-dot">.</span></div>
              <nav class="nav">
                <span>Product</span>
                <span>Why It Works</span>
                <span>Pricing</span>
                <span>Get Started</span>
              </nav>
            </div>
          </header>

          <section class="hero">
            <div class="hero-kicker">Campaign Preview</div>
            <h1>Build a real landing page experience from your generated ad copy.</h1>
            <p>Structured for users, not logs. This preview shows final campaign-ready messaging that can later be paired with brand images, logo assets, and product visuals.</p>
          </section>

          <main class="content">
            ${creativeRows ? `<div class="variant-grid">${creativeRows}</div>` : `<div class="empty">No creative variants are available yet.</div>`}
          </main>

          <footer class="content" style="padding-top:0;">
            <div style="color:#7a8590;font-size:12px;">Generated by ${esc(cleanNodeLabel(mindraContentOutput.name))} · Status: ${esc(mindraContentOutput.status)}</div>
          </footer>
        </body>
      </html>
    `;

    const blob = new Blob([html], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    const tab = window.open(url, "_blank");
    if (!tab) {
      URL.revokeObjectURL(url);
      setError("Popup blocked. Please allow popups and try again.");
      return;
    }
    window.setTimeout(() => URL.revokeObjectURL(url), 60000);
  }

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
      buySellState: toText(responseData?.buy_sell_signal, "HOLD"),
      buySellNote: toText(responseData?.buy_sell_note, "Run campaign to compute buy/sell guidance."),
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

  const mindraVersion = useMemo(() => toText(responseData?.mindra_version, ""), [responseData]);

  async function handleRunCampaign() {
    setIsRunning(true);
    setError(null);

    try {
      const result = await runMindraCampaign(brief);
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
            {mindraVersion && (
              <p className="mt-1 text-xs text-emerald-700">
                Live orchestration source: <span className="font-medium">backend orchestration API</span> ({mindraVersion})
              </p>
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              className="rounded-full bg-white px-3 py-1 text-xs shadow-sm ring-1 ring-gray-200 disabled:cursor-not-allowed disabled:opacity-50"
              onClick={openMindraContentTab}
              disabled={!mindraContentOutput}
            >
              Open Content Output
            </button>
            <button
              className="rounded-full bg-white px-3 py-1 text-xs shadow-sm ring-1 ring-gray-200 disabled:cursor-not-allowed disabled:opacity-50"
              onClick={openDiagramTab}
              disabled={!mindraTree.length}
            >
              Open Diagram
            </button>
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
                {isRunning ? "Running Orchestration..." : "Run Orchestration"}
              </button>

              {error && (
                <div className="rounded-xl bg-red-50 px-3 py-2 text-xs text-red-700 ring-1 ring-red-200">
                  {error}
                </div>
              )}

              <div className="rounded-xl bg-gray-50 px-3 py-2 text-xs text-gray-600 ring-1 ring-gray-200">
                Next: this button calls <span className="font-medium">/mindra/run</span> and streams orchestration state.
              </div>
            </div>
          </div>

          {/* Vendor Pipeline */}
          <div className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-200">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold">Vendor Pipeline</h2>
              <button
                className="rounded-full bg-white px-3 py-1 text-xs ring-1 ring-gray-200 disabled:cursor-not-allowed disabled:opacity-50"
                onClick={openWebsiteOutputTab}
                disabled={!websiteAgentOutput}
              >
                Open Website Output
              </button>
            </div>
            <p className="mt-1 text-xs text-gray-500">Requested → Paid → Delivered</p>

            <div className="mt-4 space-y-3">
              {vendorStatuses.map((v) => (
                <div key={v.label} className="flex items-center justify-between rounded-2xl bg-gray-50 p-4 ring-1 ring-gray-200">
                  <div className="text-sm font-medium">{v.label}</div>
                  <span className={`rounded-full px-3 py-1 text-xs ring-1 ${statusTone(v.status)}`}>
                    {v.status}
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
                  <div className="font-medium">Buy / Sell</div>
                  <span className="rounded-full bg-gray-100 px-3 py-1 text-xs">📈 {kpis.buySellState}</span>
                </div>
                <div className="mt-2 text-gray-600">{kpis.buySellNote}</div>
              </div>

              <div className="mt-3 rounded-xl bg-white p-3 text-xs ring-1 ring-gray-200">
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

        <div className="mt-8 text-xs text-gray-500">Demo mode fallback is enabled when paid execution is unavailable.</div>

        <div className="mt-8 rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-200">
          <h2 className="text-sm font-semibold">Nevermined Journey: Setup to Revenue</h2>
          <p className="mt-1 text-xs text-gray-500">
            Structured onboarding and monetization flow rendered from content, so you can update instructions without editing UI markup.
          </p>

          <div className="mt-5 grid gap-4">
            {neverminedJourney.map((section, sectionIndex) => (
              <div key={section.title} className="rounded-2xl bg-gray-50 p-4 ring-1 ring-gray-200">
                <div className="text-sm font-semibold">
                  {sectionIndex + 1}. {section.title}
                </div>
                <ol className="mt-2 list-decimal space-y-1 pl-5 text-xs text-gray-700">
                  {section.steps.map((step) => (
                    <li key={step}>{step}</li>
                  ))}
                </ol>
                {section.tip && (
                  <div className="mt-3 rounded-xl bg-white px-3 py-2 text-xs text-gray-600 ring-1 ring-gray-200">
                    Tip: {section.tip}
                  </div>
                )}
              </div>
            ))}
          </div>

          <div className="mt-6 rounded-2xl bg-gray-50 p-4 ring-1 ring-gray-200">
            <h3 className="text-sm font-semibold">{monetizationGuidance.heading}</h3>
            <p className="mt-2 text-xs text-gray-600">{monetizationGuidance.summary}</p>
            <p className="mt-2 text-xs font-medium text-gray-700">{monetizationGuidance.maximizeRevenue}</p>

            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {paymentRails.map((rail) => (
                <div key={rail.title} className="rounded-xl bg-white p-3 ring-1 ring-gray-200">
                  <div className="text-xs font-semibold text-gray-800">{rail.title}</div>
                  <ul className="mt-2 list-disc space-y-1 pl-4 text-xs text-gray-600">
                    {rail.points.map((point) => (
                      <li key={point}>{point}</li>
                    ))}
                  </ul>
                  {rail.footnote && <div className="mt-2 text-xs text-gray-500">{rail.footnote}</div>}
                </div>
              ))}
            </div>
          </div>

          <div className="mt-6 rounded-2xl bg-gray-50 p-4 ring-1 ring-gray-200">
            <h3 className="text-sm font-semibold">What Makes an Agent Marketplace-Ready</h3>
            <div className="mt-3 space-y-2">
              {marketplaceReadiness.map((item) => (
                <div key={item.field} className="rounded-xl bg-white px-3 py-2 text-xs ring-1 ring-gray-200">
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-medium text-gray-800">{item.field}</span>
                    <span className="rounded-full bg-gray-100 px-2 py-1 text-[11px] text-gray-600">{item.status}</span>
                  </div>
                  <div className="mt-1 text-gray-600">{item.description}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-6 rounded-2xl bg-gray-50 p-4 ring-1 ring-gray-200">
            <h3 className="text-sm font-semibold">Key Resources</h3>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {resourceLinks.map((resource) => (
                <div key={resource.label} className="rounded-xl bg-white px-3 py-2 text-xs ring-1 ring-gray-200">
                  <div className="font-medium text-gray-800">{resource.label}</div>
                  <div className="mt-1 text-gray-600">{resource.value}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
