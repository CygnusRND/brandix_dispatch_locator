{
    'name': 'Brandix Dispatch Locator & Parcel Rack Map',
    'version': '19.0.1.0.7',
    'summary': 'Smart Board Dispatch & Parcel Locator with Real-Time Component Readiness and Rack History',
    'description': """
Brandix Dispatch Locator & Rack Map Dashboard (Odoo 19)
========================================================
Architected & Developed by Cygnus One (Pvt) Ltd for Brandix Apparel Limited.

Key Features:
-------------
1. Smart Board Touch Terminal UI:
   - High-contrast touch UI optimized for warehouse floor Smart Boards and touchscreen tablets.
   - Quick numeric/code touch keypad for operators entering numbers from paper slips.

2. Instant Search & Cross-Referencing:
   - Search by Docket Number (e.g. JG5-J:856194-000).
   - Search by Schedule Number (e.g. 1384507) to list all related dockets.
   - Search by Rack/Bin Location (e.g. RACK 1) to see all stored parcels.

3. Physical Storage Rack Grid (Parcel Locator):
   - Clear visual boxes for each cut panel parcel indicating its assigned physical rack.
   - Quick rack reassignment and real-time movement logging.

4. Component Readiness & Dispatch Traffic Light:
   - Trims status verification: In-store bin location vs already dispatched with carrier docket.
   - Embellishment (EMB) pool balance checking for embellishment styles.
   - Traffic light decision header (READY TO ISSUE TO LINE / BLOCKED / ALREADY DISPATCHED).

5. Location Audit History:
   - Tracks every movement of a parcel between racks with timestamp, operator, and notes.
    """,
    'author': 'Charitha/CygnusOne',
    'website': 'https://www.cygnusonesl.com',
    'category': 'Inventory/Manufacturing',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'web',
        'stock',
        'docket_inventory_management',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/parcel_location_history_views.xml',
        'views/dispatch_locator_views.xml',
        'views/dispatch_locator_menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'brandix_dispatch_locator/static/src/scss/dispatch_locator_dashboard.scss',
            'brandix_dispatch_locator/static/src/js/dispatch_locator_dashboard.js',
            'brandix_dispatch_locator/static/src/xml/dispatch_locator_dashboard.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
