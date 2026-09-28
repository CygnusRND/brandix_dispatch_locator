# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _sync_docket_status_on_done(self):
        res = super()._sync_docket_status_on_done()
        if self.env.context.get('in_docket_line_clearance'):
            return res

        Locator = self.env['brandix.dispatch.locator'].sudo()
        for picking in self:
            if picking.is_docket_delivery and picking.state == 'done':
                try:
                    dockets = picking._find_related_dockets() if hasattr(picking, '_find_related_dockets') else self.env['product.template']
                    if not dockets and picking.docket_id:
                        dockets = picking.docket_id
                    for doc in dockets:
                        Locator.with_context(in_docket_line_clearance=True)._clear_parcels_on_line_issue(doc)
                except Exception as e:
                    _logger.exception("Error clearing parcels on picking delivery done (%s): %s", picking.name, str(e))
        return res
