# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)

class BrandixDispatchLocator(models.TransientModel):
    _name = 'brandix.dispatch.locator'
    _description = 'Dispatch & Locator Dashboard Service'

    @api.model
    def search_dispatch_data(self, search_term):
        """
        Unified Smart Search for Smart Board Dashboard:
        Searches by Docket Number, Schedule Number, Style Code, or Location/Rack name.
        Returns comprehensive real-time status and physical locations.
        """
        try:
            if not search_term or not str(search_term).strip():
                return {'status': 'empty'}

            term = str(search_term).strip()
            clean_term = term.upper()
            if ':' in clean_term:
                job_core = clean_term.split(':')[-1].strip()
            else:
                job_core = clean_term

            ProductTemplate = self.env['product.template'].sudo()
            ScheduleMaster = self.env['brandix.schedule.master'].sudo() if 'brandix.schedule.master' in self.env else None
            StockLocation = self.env['stock.location'].sudo()

            # 1. First Priority: Check if search matches a Docket Master
            docket = ProductTemplate.search([
                ('is_docket', '=', True),
                ('active', '=', True),
                '|', '|',
                ('name', '=ilike', clean_term),
                ('name', '=ilike', f"%{job_core}%"),
                ('docket_number', '=ilike', clean_term)
            ], limit=1)

            if docket:
                return self._build_docket_details(docket)

            # 2. Second Priority: Check if search matches a Schedule Number
            sched_recs = ScheduleMaster.search([
                ('name', '=ilike', clean_term)
            ], limit=1) if ScheduleMaster else None

            if not sched_recs:
                matching_dockets = ProductTemplate.search([
                    ('is_docket', '=', True),
                    ('active', '=', True),
                    ('schedule_no', '=ilike', f"%{clean_term}%")
                ])
                if matching_dockets:
                    return self._build_schedule_details_from_dockets(clean_term, matching_dockets)
            else:
                return self._build_schedule_details(sched_recs[0])

            # 3. Third Priority: Check if search matches a Style Code
            style_dockets = ProductTemplate.search([
                ('is_docket', '=', True),
                ('active', '=', True),
                '|',
                ('style_code', '=ilike', clean_term),
                ('style_code', '=ilike', f"%{clean_term}%")
            ], order='id asc')

            if style_dockets:
                return self._build_schedule_details_from_dockets(f"Style: {clean_term}", style_dockets)

            # 4. Fourth Priority: Check if search matches a Location (Rack / Bin)
            location = StockLocation.search([
                ('usage', '=', 'internal'),
                '|', '|',
                ('name', '=ilike', clean_term),
                ('name', '=ilike', f"%{clean_term}%"),
                ('complete_name', '=ilike', f"%{clean_term}%")
            ], limit=1)

            if location:
                return self._build_location_details(location)

            return {
                'status': 'not_found',
                'search_term': term,
                'message': _("No Docket, Schedule, Style, or Rack found matching '%s'") % term
            }
        except Exception as e:
            _logger.exception("Error executing dispatch locator search for '%s': %s", search_term, str(e))
            return {
                'status': 'not_found',
                'search_term': str(search_term),
                'message': _("Error searching for '%s': %s") % (search_term, str(e))
            }

    @api.model
    def _build_docket_details(self, docket):
        """Constructs full real-time dispatch and locator payload for a Docket"""
        docket.ensure_one()

        # Related Schedule Master
        sched = docket.schedule_master_ids[:1] or docket.schedule_master_id
        if not sched and docket.schedule_no and 'brandix.schedule.master' in self.env:
            sched_names = [s.strip() for s in str(docket.schedule_no).replace(';', ',').split(',') if s.strip()]
            sched = self.env['brandix.schedule.master'].sudo().search([('name', 'in', sched_names)], limit=1)

        # 1. Job Information
        job_info = {
            'docket_id': docket.id,
            'docket_no': docket.name,
            'schedule_no': docket.schedule_no or (sched.name if sched else '-'),
            'style_code': docket.style_code or (sched.style_code if sched else '-'),
            'buyer_customer': docket.buyer_customer or (sched.buyer_customer if sched else '-'),
            'color_name': docket.color_name or (sched.color_name if sched else '-'),
            'module_fr': docket.fr_module or docket.module or '-',
            'co_qty': docket.co_qty or (sched.co_qty if sched else 0.0),
            'style_type': docket.style_type or 'non_emb',
            'style_type_label': 'EMBELLISHMENT (EMB)' if docket.style_type == 'emb' else 'NON-EMB',
            'delivery_status': docket.delivery_status or 'pending',
            'is_label_printed': bool(docket.is_label_printed or docket.label_status == 'printed'),
        }

        # 2. Panel Cut Parcels & Their Physical Racks
        parcels_data = []
        grn_pickings = self.env['stock.picking'].sudo().search([
            ('is_docket_grn', '=', True),
            ('state', '!=', 'cancel'),
            '|', ('docket_id', '=', docket.id), ('job_number', '=ilike', docket.name)
        ])

        for grn in grn_pickings:
            for p_loc in grn.parcel_location_ids:
                parcels_data.append({
                    'id': p_loc.id,
                    'parcel_number': p_loc.parcel_number,
                    'parcel_name': p_loc.parcel_name or f"Parcel #{p_loc.parcel_number}",
                    'location_id': p_loc.location_dest_id.id if p_loc.location_dest_id else False,
                    'location_name': p_loc.location_dest_id.name if p_loc.location_dest_id else 'UNASSIGNED',
                    'location_full_name': p_loc.location_dest_id.complete_name if p_loc.location_dest_id else 'Not Placed Yet',
                    'grn_name': grn.name,
                    'grn_state': grn.state,
                    'history_count': p_loc.history_count if hasattr(p_loc, 'history_count') else 0,
                })

        # 3. Trims Readiness & Location
        trims_status = docket.trims_status or (sched.trims_status if sched else 'pending')
        carrier_docket_name = docket.trims_issued_with_docket_id.name if docket.trims_issued_with_docket_id else ''
        if not carrier_docket_name and sched and sched.first_issued_docket_id:
            carrier_docket_name = sched.first_issued_docket_id.name
        trims_issued_date = fields.Datetime.to_string(sched.trims_issued_date) if sched and sched.trims_issued_date else ''

        # Search Trims physical location in warehouse if in store
        trims_location = 'Not Assigned'
        if sched:
            trims_pick = self.env['stock.picking'].sudo().search([
                ('is_component_receipt', '=', True),
                ('style_type', '=', 'trims'),
                ('schedule_master_id', '=', sched.id),
                ('state', '!=', 'cancel')
            ], limit=1)
            if trims_pick and trims_pick.destination_bin_id:
                trims_location = trims_pick.destination_bin_id.name

        trims_info = {
            'status': trims_status,
            'is_ready': trims_status in ('issued', 'already_issued') or (docket.delivery_status == 'done'),
            'is_carrier': docket.trims_status == 'issued',
            'is_already_issued': docket.trims_status == 'already_issued',
            'carrier_docket': carrier_docket_name,
            'issued_date': trims_issued_date,
            'location_name': trims_location
        }

        # 4. Embellishment (EMB) Pool & Status
        is_emb = (docket.style_type == 'emb')
        emb_pool_balance = sched.emb_pool_balance if sched else 0.0
        emb_pool_received = sched.emb_pool_received if sched else 0.0
        emb_status = docket.emb_status or (sched.emb_status if sched else 'pending')

        # Find EMB Physical Rack/Bin
        emb_location = 'Not Assigned'
        if is_emb and sched:
            emb_pick = self.env['stock.picking'].sudo().search([
                ('is_component_receipt', '=', True),
                ('style_type', '=', 'emb'),
                ('schedule_master_id', '=', sched.id),
                ('state', '!=', 'cancel')
            ], limit=1)
            if emb_pick and emb_pick.destination_bin_id:
                emb_location = emb_pick.destination_bin_id.name

        emb_info = {
            'is_emb_style': is_emb,
            'status': emb_status,
            'is_ready': (not is_emb) or (emb_status == 'ready') or (docket.delivery_status == 'done'),
            'pool_balance': emb_pool_balance,
            'pool_received': emb_pool_received,
            'location_name': emb_location
        }

        # 5. Master Dispatch Decision (Traffic Light)
        if docket.delivery_status == 'done':
            decision = {
                'can_issue': False,
                'state': 'already_dispatched',
                'color': 'blue',
                'badge_class': 'decision-dispatched bg-primary text-white',
                'banner_title': _("ALREADY DISPATCHED TO SEWING LINE"),
                'banner_subtitle': _("This Docket has already been fully issued and sent out to the sewing floor.")
            }
        elif not trims_info['is_ready']:
            decision = {
                'can_issue': False,
                'state': 'blocked_trims',
                'color': 'red',
                'badge_class': 'decision-blocked bg-danger text-white',
                'banner_title': _("DO NOT ISSUE - TRIMS PENDING!"),
                'banner_subtitle': _("Required Trims components have not been received in store yet.")
            }
        elif is_emb and not emb_info['is_ready']:
            decision = {
                'can_issue': False,
                'state': 'blocked_emb',
                'color': 'red',
                'badge_class': 'decision-blocked bg-danger text-white',
                'banner_title': _("DO NOT ISSUE - EMBELLISHMENT PENDING!"),
                'banner_subtitle': _("Insufficient EMB pool balance for this schedule. Cannot dispatch until received.")
            }
        else:
            decision = {
                'can_issue': True,
                'state': 'ready_to_issue',
                'color': 'green',
                'badge_class': 'decision-ready bg-success text-white',
                'banner_title': _("ALL COMPONENTS READY - CAN ISSUE TO LINE!"),
                'banner_subtitle': _("All Cut Parcels, Trims, and Embellishments are verified and available.")
            }

        return {
            'status': 'success',
            'query_type': 'docket',
            'job': job_info,
            'parcels': parcels_data,
            'trims': trims_info,
            'emb': emb_info,
            'decision': decision
        }

    @api.model
    def _build_schedule_details(self, sched):
        """Constructs full schedule-wise multi-docket payload"""
        sched.ensure_one()
        ProductTemplate = self.env['product.template'].sudo()

        dockets = ProductTemplate.search([
            ('is_docket', '=', True),
            ('active', '=', True),
            '|', '|',
            ('schedule_master_ids', 'in', [sched.id]),
            ('schedule_master_id', '=', sched.id),
            ('schedule_no', '=ilike', f"%{sched.name}%")
        ], order='id asc')

        dockets_summary = []
        for doc in dockets:
            doc_data = self._build_docket_details(doc)
            dockets_summary.append({
                'docket_id': doc.id,
                'docket_no': doc.name,
                'co_qty': doc.co_qty,
                'module_fr': doc.fr_module or doc.module or '-',
                'delivery_status': doc.delivery_status or 'pending',
                'can_issue': doc_data['decision']['can_issue'],
                'decision': doc_data['decision'],
                'parcels': doc_data['parcels'],
                'trims': doc_data['trims'],
                'emb': doc_data['emb']
            })

        return {
            'status': 'success',
            'query_type': 'schedule',
            'schedule': {
                'id': sched.id,
                'schedule_no': sched.name,
                'style_code': sched.style_code or '-',
                'buyer_customer': sched.buyer_customer or '-',
                'color_name': sched.color_name or '-',
                'co_qty': sched.co_qty or 0.0,
                'mo_qty': sched.mo_qty or 0.0,
                'style_type': sched.style_type or 'non_emb',
                'style_type_label': 'EMBELLISHMENT (EMB)' if sched.style_type == 'emb' else 'NON-EMB',
                'trims_status': sched.trims_status or 'pending',
                'first_issued_docket': sched.first_issued_docket_id.name if sched.first_issued_docket_id else '',
                'trims_issued_date': fields.Datetime.to_string(sched.trims_issued_date) if sched.trims_issued_date else '',
                'emb_pool_balance': sched.emb_pool_balance,
                'emb_pool_received': sched.emb_pool_received,
                'total_dockets_count': len(dockets_summary),
                'ready_dockets_count': len([d for d in dockets_summary if d['can_issue']]),
            },
            'dockets': dockets_summary
        }

    @api.model
    def _build_schedule_details_from_dockets(self, sched_name, dockets):
        """Fallback when schedule master model is not used directly"""
        first_doc = dockets[0]
        dockets_summary = []
        for doc in dockets:
            doc_data = self._build_docket_details(doc)
            dockets_summary.append({
                'docket_id': doc.id,
                'docket_no': doc.name,
                'co_qty': doc.co_qty,
                'module_fr': doc.fr_module or doc.module or '-',
                'delivery_status': doc.delivery_status or 'pending',
                'can_issue': doc_data['decision']['can_issue'],
                'decision': doc_data['decision'],
                'parcels': doc_data['parcels'],
                'trims': doc_data['trims'],
                'emb': doc_data['emb']
            })

        return {
            'status': 'success',
            'query_type': 'schedule',
            'schedule': {
                'id': 0,
                'schedule_no': sched_name,
                'style_code': first_doc.style_code or '-',
                'buyer_customer': first_doc.buyer_customer or '-',
                'color_name': first_doc.color_name or '-',
                'co_qty': sum(d.co_qty or 0 for d in dockets),
                'mo_qty': 0.0,
                'style_type': first_doc.style_type or 'non_emb',
                'style_type_label': 'EMBELLISHMENT (EMB)' if first_doc.style_type == 'emb' else 'NON-EMB',
                'trims_status': first_doc.trims_status or 'pending',
                'first_issued_docket': first_doc.trims_issued_with_docket_id.name if first_doc.trims_issued_with_docket_id else '',
                'trims_issued_date': '',
                'emb_pool_balance': 0.0,
                'emb_pool_received': 0.0,
                'total_dockets_count': len(dockets_summary),
                'ready_dockets_count': len([d for d in dockets_summary if d['can_issue']]),
            },
            'dockets': dockets_summary
        }

    @api.model
    def _build_location_details(self, location):
        """Returns all items currently stored in a given Rack/Bin location"""
        location.ensure_one()
        ParcelLoc = self.env['brandix.docket.parcel.location'].sudo()

        parcel_recs = ParcelLoc.search([
            ('location_dest_id', '=', location.id)
        ])

        stored_items = []
        for p in parcel_recs:
            picking = p.picking_id
            if picking and picking.state != 'cancel':
                docket = picking.docket_id
                stored_items.append({
                    'parcel_id': p.id,
                    'parcel_name': p.parcel_name or f"Parcel #{p.parcel_number}",
                    'parcel_number': p.parcel_number,
                    'docket_no': docket.name if docket else (picking.job_number or '-'),
                    'schedule_no': docket.schedule_no if docket else '-',
                    'style_code': docket.style_code if docket else '-',
                    'color_name': docket.color_name if docket else '-',
                    'module_fr': docket.fr_module if docket else '-',
                    'grn_name': picking.name,
                    'history_count': p.history_count if hasattr(p, 'history_count') else 0
                })

        return {
            'status': 'success',
            'query_type': 'location',
            'location': {
                'id': location.id,
                'name': location.name,
                'complete_name': location.complete_name,
                'total_items': len(stored_items)
            },
            'items': stored_items
        }

    @api.model
    def get_warehouse_racks_overview(self):
        """Fetches all warehouse internal racks/bins with real-time parcel counts"""
        try:
            StockLocation = self.env['stock.location'].sudo()
            ParcelLoc = self.env['brandix.docket.parcel.location'].sudo()

            locations = StockLocation.search([
                ('usage', '=', 'internal'),
                ('location_id', '!=', False)
            ], order='name asc')

            racks = []
            for loc in locations:
                count = ParcelLoc.search_count([
                    ('location_dest_id', '=', loc.id),
                    ('picking_id.state', 'not in', ('done', 'cancel'))
                ])
                done_count = ParcelLoc.search_count([
                    ('location_dest_id', '=', loc.id),
                    ('picking_id.state', '=', 'done')
                ])
                racks.append({
                    'id': loc.id,
                    'name': loc.name,
                    'complete_name': loc.complete_name,
                    'active_parcel_count': count,
                    'done_parcel_count': done_count,
                    'total_count': count + done_count
                })

            return racks
        except Exception as e:
            _logger.exception("Error in get_warehouse_racks_overview: %s", str(e))
            return []

    @api.model
    def get_parcel_location_history(self, parcel_location_id):
        """Returns the full audit trail of location movements for a parcel"""
        try:
            History = self.env['brandix.docket.parcel.location.history'].sudo()
            logs = History.search([
                ('parcel_location_id', '=', int(parcel_location_id))
            ], order='change_date desc, id desc')

            return [{
                'id': h.id,
                'parcel_name': h.parcel_name,
                'old_location': h.old_location_name or 'Unassigned',
                'new_location': h.new_location_name or 'Unassigned',
                'user_name': h.user_id.name if h.user_id else 'System',
                'change_date': fields.Datetime.to_string(h.change_date),
                'notes': h.notes or ''
            } for h in logs]
        except Exception as e:
            _logger.exception("Error in get_parcel_location_history: %s", str(e))
            return []

    @api.model
    def reassign_parcel_location(self, parcel_location_id, new_location_id, reason="Manual Smart Board Reassignment"):
        """Directly relocates a parcel from the Smart Board and logs audit trail"""
        try:
            ParcelLoc = self.env['brandix.docket.parcel.location'].sudo()
            parcel = ParcelLoc.browse(int(parcel_location_id))
            if not parcel.exists():
                return {'success': False, 'message': 'Parcel not found'}

            parcel.with_context(location_change_reason=reason).write({
                'location_dest_id': int(new_location_id)
            })

            return {
                'success': True,
                'location_name': parcel.location_dest_id.name,
                'location_full_name': parcel.location_dest_id.complete_name
            }
        except Exception as e:
            _logger.exception("Error in reassign_parcel_location: %s", str(e))
            return {'success': False, 'message': str(e)}
