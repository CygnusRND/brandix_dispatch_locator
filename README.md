# Brandix Dispatch Locator & Parcel Rack Map Dashboard

**Brandix Apparel Limited x Cygnus One (Pvt) Ltd**  
Odoo 19 Enterprise Module for Smart Board Warehouse Dispatch and Cut Panel Parcel Rack Tracking.

---

## Overview
This module introduces an industrial Smart Board Touch Terminal dashboard specifically designed for factory cutting and warehouse dispatch teams at Brandix.

When floor workers bring a paper slip with a **Docket Number** or **Schedule Number**, this terminal provides an instant, touch-friendly verification of:
1. **Cut Panel Parcels & Storage Racks**: Instant visual location layout displaying which physical rack/bin (e.g., Rack 1, Rack 2) holds each parcel.
2. **Trims Component Readiness**: Real-time cross-referencing to check whether trims are in store (with bin location) or already dispatched schedule-wise with another carrier docket.
3. **Embellishment (EMB) Pool Balance**: Live validation of EMB pool availability for embellishment styles.
4. **Master Traffic Light Decision Banner**: Clear 5-meter visual indicator (**🟢 READY TO ISSUE** / **🔴 DO NOT ISSUE - BLOCKED** / **🔵 ALREADY DISPATCHED**).
5. **Interactive Warehouse Rack Map**: Visual grid of all warehouse racks showing current stored parcel counts and inventory breakdown.
6. **Location Movement Audit Trail**: Automatically tracks every physical move of a parcel between racks (date, operator, old location, new location, notes).

---

## Features
- **Smart Board / Touch Tablet UI**: OWL-based frontend with touch numpad, big action buttons, and full-screen kiosk mode.
- **Unified Smart Search**: Search interchangeably by Docket No, Schedule No, or Rack/Bin Name.
- **In-Place Rack Reassignment**: Relocate parcels directly from the Smart Board with real-time audit logging.
- **Strict Architecture Isolation**: Extends Brandix inventory models non-invasively with zero modifications to core addons.

---

## Installation & Requirements
- **Odoo Version**: 19.0 (Enterprise / Community / Odoo.sh)
- **Dependencies**: `base`, `web`, `stock`, `docket_inventory_management`

Developed with ❤️ by **Cygnus One (Pvt) Ltd**.
