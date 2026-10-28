// GENERATED FILE — do not edit by hand.
// Regenerate with: uv run ontology export-web
import type { ObjectTypeName } from "./objects";export const LINKS: Record<
  string,
  { target: ObjectTypeName; cardinality: 'one' | 'many' }[]
> = {
  ActionProposal: [
    { target: "AgentRun", cardinality: "one" }, // agentRun
  ],
  AgentRun: [
    { target: "ActionProposal", cardinality: "many" }, // proposals
  ],
  Batch: [
    { target: "Product", cardinality: "one" }, // product
    { target: "Store", cardinality: "one" }, // store
  ],
  Product: [
    { target: "Batch", cardinality: "many" }, // batches
  ],
  Store: [
    { target: "Batch", cardinality: "many" }, // batches
  ],
};
