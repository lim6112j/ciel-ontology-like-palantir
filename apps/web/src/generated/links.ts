// GENERATED FILE — do not edit by hand.
// Regenerate with: uv run ontology export-client --out apps/web/src/generated
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
  Delivery: [
    { target: "DeliveryStop", cardinality: "many" }, // stops
    { target: "Driver", cardinality: "one" }, // driver
    { target: "Vehicle", cardinality: "one" }, // vehicle
    { target: "Depot", cardinality: "one" }, // depot
    { target: "DeliveryRoute", cardinality: "one" }, // route
  ],
  DeliveryRoute: [
    { target: "Outlet", cardinality: "many" }, // outlets
    { target: "Delivery", cardinality: "many" }, // deliveries
    { target: "Depot", cardinality: "one" }, // depot
    { target: "SalesRep", cardinality: "one" }, // salesRep
  ],
  DeliveryStop: [
    { target: "Outlet", cardinality: "one" }, // outlet
    { target: "SalesOrder", cardinality: "many" }, // orders
    { target: "SalesInvoice", cardinality: "one" }, // invoice
    { target: "Delivery", cardinality: "one" }, // delivery
  ],
  Depot: [
    { target: "Outlet", cardinality: "many" }, // outlets
    { target: "Delivery", cardinality: "many" }, // deliveries
    { target: "Driver", cardinality: "many" }, // drivers
    { target: "Vehicle", cardinality: "many" }, // vehicles
    { target: "DeliveryRoute", cardinality: "many" }, // routes
    { target: "SalesRep", cardinality: "many" }, // salesReps
  ],
  Driver: [
    { target: "Delivery", cardinality: "many" }, // deliveries
    { target: "Depot", cardinality: "one" }, // depot
    { target: "DriverShift", cardinality: "many" }, // shifts
  ],
  DriverShift: [
    { target: "Driver", cardinality: "one" }, // driver
  ],
  InvoiceLine: [
    { target: "SalesInvoice", cardinality: "one" }, // invoice
    { target: "Product", cardinality: "one" }, // product
  ],
  Outlet: [
    { target: "SalesRep", cardinality: "one" }, // salesRep
    { target: "Depot", cardinality: "one" }, // depot
    { target: "SalesOrder", cardinality: "many" }, // orders
    { target: "DeliveryRoute", cardinality: "one" }, // route
    { target: "DeliveryStop", cardinality: "many" }, // stops
  ],
  Product: [
    { target: "SalesOrderLine", cardinality: "many" }, // orderLines
    { target: "InvoiceLine", cardinality: "many" }, // invoiceLines
  ],
  SalesInvoice: [
    { target: "SalesOrder", cardinality: "one" }, // order
    { target: "InvoiceLine", cardinality: "many" }, // lines
    { target: "DeliveryStop", cardinality: "one" }, // stop
  ],
  SalesOrder: [
    { target: "Outlet", cardinality: "one" }, // outlet
    { target: "SalesRep", cardinality: "one" }, // salesRep
    { target: "SalesOrderLine", cardinality: "many" }, // lines
    { target: "SalesInvoice", cardinality: "many" }, // invoices
    { target: "DeliveryStop", cardinality: "one" }, // stop
  ],
  SalesOrderLine: [
    { target: "SalesOrder", cardinality: "one" }, // order
    { target: "Product", cardinality: "one" }, // product
  ],
  SalesRep: [
    { target: "Outlet", cardinality: "many" }, // outlets
    { target: "SalesOrder", cardinality: "many" }, // orders
    { target: "DeliveryRoute", cardinality: "many" }, // routes
    { target: "Depot", cardinality: "one" }, // depot
  ],
  Vehicle: [
    { target: "Delivery", cardinality: "many" }, // deliveries
    { target: "Depot", cardinality: "one" }, // depot
  ],
};
