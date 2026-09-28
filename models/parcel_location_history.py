# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class BrandixDocketParcelLocationHistory(models.Model):
    _name = 'brandix.docket.parcel.location.history'
    _description = 'Docket Parcel Location Audit Trail'
    _order = 'change_date desc, id desc'

    parcel_location_id = fields.Many2one(
        'brandix.docket.parcel.location',
        string="Parcel Reference",
        ondelete='cascade',
        index=True
    )
    picking_id = fields.Many2one(
        'stock.picking',
        string="Docket GRN",
        related='parcel_location_id.picking_id',
        readonly=True
    )
    docket_id = fields.Many2one(
        'product.template',
        string="Docket Master",
        related='parcel_location_id.picking_id.docket_id',
        readonly=True
    )
    parcel_number = fields.Integer(string="Parcel #")
    parcel_name = fields.Char(string="Parcel Name")
    old_location_id = fields.Many2one(
        'stock.location',
        string="Previous Rack / Bin",
        domain="[('usage', '=', 'internal')]"
    )
    new_location_id = fields.Many2one(
        'stock.location',
        string="New Rack / Bin",
        domain="[('usage', '=', 'internal')]"
    )
    old_location_name = fields.Char(string="Previous Location Name")
    new_location_name = fields.Char(string="New Location Name")
    user_id = fields.Many2one(
        'res.users',
        string="Changed By",
        default=lambda self: self.env.user,
        index=True
    )
    change_date = fields.Datetime(
        string="Changed On",
        default=fields.Datetime.now,
        index=True
    )
    notes = fields.Char(string="Notes / Source")


class BrandixDocketParcelLocation(models.Model):
    _inherit = 'brandix.docket.parcel.location'

    history_ids = fields.One2many(
        'brandix.docket.parcel.location.history',
        'parcel_location_id',
        string="Location History"
    )
    history_count = fields.Integer(
        string="History Count",
        compute='_compute_history_count'
    )

    @api.depends('history_ids')
    def _compute_history_count(self):
        for rec in self:
            rec.history_count = len(rec.history_ids)

    def write(self, vals):
        if 'location_dest_id' in vals:
            History = self.env['brandix.docket.parcel.location.history'].sudo()
            Location = self.env['stock.location'].sudo()
            new_loc_id = vals.get('location_dest_id')
            new_loc = Location.browse(new_loc_id) if new_loc_id else False
            new_loc_name = new_loc.display_name if new_loc else 'Unassigned'

            for rec in self:
                old_loc_id = rec.location_dest_id.id if rec.location_dest_id else False
                if old_loc_id != new_loc_id:
                    old_loc_name = rec.location_dest_id.display_name if rec.location_dest_id else 'Unassigned'
                    docket = rec.picking_id.docket_id if rec.picking_id else False
                    History.create({
                        'parcel_location_id': rec.id,
                        'parcel_number': rec.parcel_number,
                        'parcel_name': rec.parcel_name or f"Parcel #{rec.parcel_number}",
                        'old_location_id': old_loc_id,
                        'new_location_id': new_loc_id,
                        'old_location_name': old_loc_name,
                        'new_location_name': new_loc_name,
                        'user_id': self.env.user.id,
                        'change_date': fields.Datetime.now(),
                        'notes': self.env.context.get('location_change_reason') or 'Location reassignment'
                    })
        return super().write(vals)

    def action_view_history(self):
        self.ensure_one()
        return {
            'name': _('Location History for %s') % (self.parcel_name or f"Parcel #{self.parcel_number}"),
            'type': 'ir.actions.act_window',
            'res_model': 'brandix.docket.parcel.location.history',
            'view_mode': 'list,form',
            'domain': [('parcel_location_id', '=', self.id)],
            'target': 'current',
        }
