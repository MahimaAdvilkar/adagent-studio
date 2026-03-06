export type JourneyStep = {
  title: string;
  steps: string[];
  tip?: string;
};

export type PaymentRail = {
  title: string;
  points: string[];
  footnote?: string;
};

export type ReadinessField = {
  field: string;
  status: "Critical" | "Auto";
  description: string;
};

export const neverminedJourney: JourneyStep[] = [
  {
    title: "Register and Connect",
    steps: [
      "Enter your team name, short description, and competitive theme.",
      "Create a free account at nevermined.app and generate a Sandbox API key from Settings > API Keys.",
      "Paste the API key and connect. Your wallet address becomes your team identity.",
      "On first registration you receive 20 USDC on Base Sepolia to start with testnet transactions.",
      "If you are returning, you can skip directly to the API key step.",
    ],
    tip: "Your data is tied to your wallet, not your browser session. You can log out and back in anytime. The 20 USDC welcome bonus is one-time on Base Sepolia testnet.",
  },
  {
    title: "Sell and Monetize",
    steps: [
      "Register your agent on nevermined.app with a name, description, and endpoint URL.",
      "Create a payment plan with price and credits. Offer card, USDC, or both to maximize reach.",
      "Use Sync from Nevermined in this app to pull your agent and plans automatically.",
      "Complete your listing with category, services offered, and services per request.",
    ],
    tip: "Selling is optional if you only want to buy. Teams that both sell and buy usually rank higher on leaderboard volume.",
  },
  {
    title: "Buy and Discover",
    steps: [
      "Browse the marketplace to find agents offering services your team needs.",
      "Use any API key from your Nevermined account to order a plan with USDC or card. Buyer registration is not required.",
      "Create multiple API keys for different agents or services. They still map to the same Nevermined account.",
      "Call seller agents using x402 access tokens. Credits are consumed per request.",
    ],
    tip: "Keep all buying and selling under one Nevermined account so your total transaction volume counts toward one leaderboard identity.",
  },
  {
    title: "Browse the Marketplace",
    steps: [
      "Open the Marketplace tab to view all agents across teams.",
      "Filter by category, search by agent name or services, and open cards for full details.",
      "Listings update in near real time as teams sync agents and complete metadata.",
    ],
  },
];

export const paymentRails: PaymentRail[] = [
  {
    title: "Credit Card (Fiat)",
    points: [
      "Buyers enroll a card once via Stripe, then purchase plans without holding crypto.",
      "Best for enterprise teams, non-crypto users, and autonomous agents that need fiat rails.",
      "Powered by x402 card delegation with spending limits and transaction caps.",
    ],
    footnote:
      "Stripe test card: 4242 4242 4242 4242, any future expiry date, any three-digit CVC.",
  },
  {
    title: "USDC (Crypto)",
    points: [
      "Buyers pay on-chain in USDC with peer-to-peer settlement.",
      "Best for crypto-native teams and agents that already manage funded wallets.",
    ],
  },
];

export const monetizationGuidance = {
  heading: "Plans, Credits, and Payment",
  summary:
    "Each seller agent needs at least one payment plan. You set the unit price and buyers purchase coverage for one or more requests while Nevermined handles metering and settlement.",
  maximizeRevenue:
    "Create both fiat and crypto plans for each agent so every buyer can choose their preferred payment rail.",
};

export const marketplaceReadiness: ReadinessField[] = [
  {
    field: "Description",
    status: "Critical",
    description: "A clear summary of what the agent does. Often missing in on-chain records.",
  },
  {
    field: "Category",
    status: "Critical",
    description: "Needed for marketplace discovery and filtering.",
  },
  {
    field: "Services Offered",
    status: "Critical",
    description: "Comma-separated capabilities your agent can deliver.",
  },
  {
    field: "Services Per Request",
    status: "Critical",
    description: "Define what one API call includes so buyers can value the plan.",
  },
  {
    field: "Endpoint URL",
    status: "Auto",
    description: "Derived from your Nevermined agent registration.",
  },
  {
    field: "Price and Metering Unit",
    status: "Auto",
    description: "Pulled from your plan type such as per-request or time-based.",
  },
  {
    field: "Price per Request",
    status: "Auto",
    description: "Pulled from your payment plan pricing.",
  },
];

export const resourceLinks = [
  { label: "Nevermined Docs", value: "SDK reference, tutorials, and guides" },
  { label: "Nevermined App", value: "Register agents and create plans" },
  { label: "Hackathon Rules", value: "Competition details and judging criteria" },
  { label: "Discord", value: "Announcements, support, and team matching" },
];
