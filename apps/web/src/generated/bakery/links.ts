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
    { target: "Shipment", cardinality: "many" }, // shipments
    { target: "WasteRecord", cardinality: "many" }, // wasteRecords
    { target: "ProductionPlan", cardinality: "one" }, // plan
    { target: "Product", cardinality: "one" }, // product
    { target: "Store", cardinality: "one" }, // store
  ],
  Product: [
    { target: "ProductionPlan", cardinality: "one" }, // plans
    { target: "Batch", cardinality: "many" }, // batches
    { target: "StoreStock", cardinality: "many" }, // stocks
  ],
  ProductionPlan: [
    { target: "Batch", cardinality: "many" }, // batches
    { target: "Product", cardinality: "many" }, // product
  ],
  Shipment: [
    { target: "Batch", cardinality: "one" }, // batch
    { target: "Store", cardinality: "one" }, // store
  ],
  Store: [
    { target: "Batch", cardinality: "many" }, // batches
    { target: "Shipment", cardinality: "many" }, // shipments
    { target: "StoreStock", cardinality: "many" }, // stocks
  ],
  StoreStock: [
    { target: "Product", cardinality: "one" }, // product
    { target: "Store", cardinality: "one" }, // store
  ],
  WasteRecord: [
    { target: "Batch", cardinality: "one" }, // batch
  ],
};
