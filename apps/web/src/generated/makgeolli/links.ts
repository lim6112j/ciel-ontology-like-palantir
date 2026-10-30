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
    { target: "TempReading", cardinality: "many" }, // readings
    { target: "WarehouseStock", cardinality: "many" }, // stocks
    { target: "WasteRecord", cardinality: "many" }, // wasteRecords
    { target: "Product", cardinality: "one" }, // product
    { target: "RawMaterial", cardinality: "many" }, // materials
    { target: "Tank", cardinality: "one" }, // tank
  ],
  Customer: [
    { target: "SalesOrder", cardinality: "many" }, // orders
    { target: "OutletStock", cardinality: "many" }, // outletStocks
    { target: "Shipment", cardinality: "many" }, // shipments
  ],
  OutletStock: [
    { target: "Customer", cardinality: "one" }, // customer
    { target: "Product", cardinality: "one" }, // product
  ],
  Product: [
    { target: "SalesOrderLine", cardinality: "many" }, // orderLines
    { target: "Batch", cardinality: "many" }, // batches
    { target: "OutletStock", cardinality: "many" }, // outletStocks
    { target: "WarehouseStock", cardinality: "many" }, // warehouseStocks
  ],
  RawMaterial: [
    { target: "Batch", cardinality: "many" }, // batches
  ],
  SalesOrder: [
    { target: "Customer", cardinality: "one" }, // customer
    { target: "SalesOrderLine", cardinality: "many" }, // lines
    { target: "Shipment", cardinality: "many" }, // shipments
  ],
  SalesOrderLine: [
    { target: "Product", cardinality: "one" }, // product
    { target: "SalesOrder", cardinality: "one" }, // order
  ],
  Shipment: [
    { target: "Batch", cardinality: "one" }, // batch
    { target: "Customer", cardinality: "one" }, // customer
    { target: "SalesOrder", cardinality: "one" }, // order
  ],
  Tank: [
    { target: "Batch", cardinality: "many" }, // batches
  ],
  TempReading: [
    { target: "Batch", cardinality: "one" }, // batch
  ],
  WarehouseStock: [
    { target: "Batch", cardinality: "one" }, // batch
    { target: "Product", cardinality: "one" }, // product
  ],
  WasteRecord: [
    { target: "Batch", cardinality: "one" }, // batch
  ],
};
