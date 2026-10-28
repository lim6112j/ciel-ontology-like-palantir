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
  Delivery: [
    { target: "Depot", cardinality: "one" }, // depot
    { target: "Driver", cardinality: "one" }, // driver
    { target: "DeliveryRoute", cardinality: "one" }, // route
    { target: "DeliveryStop", cardinality: "many" }, // stops
    { target: "Vehicle", cardinality: "one" }, // vehicle
  ],
  DeliveryRoute: [
    { target: "Delivery", cardinality: "many" }, // deliveries
    { target: "Outlet", cardinality: "many" }, // outlets
    { target: "Depot", cardinality: "one" }, // depot
    { target: "SalesRep", cardinality: "one" }, // salesRep
  ],
  DeliveryStop: [
    { target: "Delivery", cardinality: "one" }, // delivery
    { target: "SalesInvoice", cardinality: "one" }, // invoice
    { target: "SalesOrder", cardinality: "many" }, // orders
    { target: "Outlet", cardinality: "one" }, // outlet
  ],
  Depot: [
    { target: "Delivery", cardinality: "many" }, // deliveries
    { target: "Driver", cardinality: "many" }, // drivers
    { target: "Outlet", cardinality: "many" }, // outlets
    { target: "DeliveryRoute", cardinality: "many" }, // routes
    { target: "SalesRep", cardinality: "many" }, // salesReps
    { target: "Vehicle", cardinality: "many" }, // vehicles
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
    { target: "Depot", cardinality: "one" }, // depot
    { target: "SalesOrder", cardinality: "many" }, // orders
    { target: "DeliveryRoute", cardinality: "one" }, // route
    { target: "SalesRep", cardinality: "one" }, // salesRep
    { target: "DeliveryStop", cardinality: "many" }, // stops
  ],
  Product: [
    { target: "InvoiceLine", cardinality: "many" }, // invoiceLines
    { target: "SalesOrderLine", cardinality: "many" }, // orderLines
  ],
  SalesInvoice: [
    { target: "InvoiceLine", cardinality: "many" }, // lines
    { target: "DeliveryStop", cardinality: "one" }, // stop
    { target: "SalesOrder", cardinality: "one" }, // order
  ],
  SalesOrder: [
    { target: "SalesInvoice", cardinality: "many" }, // invoices
    { target: "SalesOrderLine", cardinality: "many" }, // lines
    { target: "SalesRep", cardinality: "one" }, // salesRep
    { target: "DeliveryStop", cardinality: "one" }, // stop
    { target: "Outlet", cardinality: "one" }, // outlet
  ],
  SalesOrderLine: [
    { target: "Product", cardinality: "one" }, // product
    { target: "SalesOrder", cardinality: "one" }, // order
  ],
  SalesRep: [
    { target: "SalesOrder", cardinality: "many" }, // orders
    { target: "Outlet", cardinality: "many" }, // outlets
    { target: "DeliveryRoute", cardinality: "many" }, // routes
    { target: "Depot", cardinality: "one" }, // depot
  ],
  Vehicle: [
    { target: "Delivery", cardinality: "many" }, // deliveries
    { target: "Depot", cardinality: "one" }, // depot
  ],
};
