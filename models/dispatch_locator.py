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
        Supports fuzzy and normalized input (e.g. KD-A4B9, KD - A4B9, JG5-J:KD-A4B9, partial schedules).
        Returns comprehensive real-time status and physical locations.
        """
        try:
            if not search_term or not str(search_term).strip():
                return {'status': 'empty'}

            raw = str(search_term).strip()
            raw_upper = raw.upper()
            no_spaces = raw_upper.replace(" ", "")

            # Build candidate search keys in priority order
            keys = []
            for k in [raw, raw_upper, no_spaces]:
                if k and k not in keys:
                    keys.append(k)

            # Handle colon format e.g. "JG5-J:KD-A4B9"
            if ':' in raw_upper:
                colon_part = raw_upper.split(':')[-1].strip()
                if colon_part and colon_part not in keys:
                    keys.append(colon_part)
                clean_colon = colon_part.replace(" ", "")
                if clean_colon and clean_colon not in keys:
                    keys.append(clean_colon)

            # Handle hyphen format e.g. "KD-A4B9" or "KD - A4B9"
            if '-' in raw_upper:
                no_hyphen = raw_upper.replace("-", "").replace(" ", "")
                if len(no_hyphen) >= 3 and no_hyphen not in keys:
                    keys.append(no_hyphen)
                for part in raw_upper.split('-'):
                    p = part.strip()
                    if len(p) >= 3 and p not in keys:
                        keys.append(p)

            ProductTemplate = self.env['product.template'].sudo()
            ScheduleMaster = self.env['brandix.schedule.master'].sudo() if 'brandix.schedule.master' in self.env else None
            StockLocation = self.env['stock.location'].sudo()

            # 1. First Priority: Check if search matches a Docket Master
            docket = None
            for k in keys:
                docket = ProductTemplate.search([
                    ('is_docket', '=', True),
                    ('active', '=', True),
                    '|',
                    ('name', '=ilike', k),
                    ('docket_number', '=ilike', k)
                ], limit=1)
                if docket:
                    break

            if not docket:
                for k in keys:
                    if len(k) >= 3:
                        docket = ProductTemplate.search([
                            ('is_docket', '=', True),
                            ('active', '=', True),
                            '|',
                            ('name', '=ilike', f"%{k}%"),
                            ('docket_number', '=ilike', f"%{k}%")
                        ], limit=1)
                        if docket:
                            break

            if docket:
                return self._build_docket_details(docket)

            # 2. Second Priority: Check if search matches a Schedule Number
            sched = None
            if ScheduleMaster:
                for k in keys:
                    sched = ScheduleMaster.search([
                        ('name', '=ilike', k)
                    ], limit=1)
                    if sched:
                        break
                if not sched:
                    for k in keys:
                        if len(k) >= 3:
                            sched = ScheduleMaster.search([
                                ('name', '=ilike', f"%{k}%")
                            ], limit=1)
                            if sched:
                                break

            if sched:
                return self._build_schedule_details(sched)

            # Fallback to schedule_no on product.template
            for k in keys:
                if len(k) >= 3:
                    matching_dockets = ProductTemplate.search([
                        ('is_docket', '=', True),
                        ('active', '=', True),
                        ('schedule_no', '=ilike', f"%{k}%")
                    ])
                    if matching_dockets:
                        return self._build_schedule_details_from_dockets(k, matching_dockets)

            # 3. Third Priority: Check if search matches a Style Code
            for k in keys:
                if len(k) >= 3:
                    style_dockets = ProductTemplate.search([
                        ('is_docket', '=', True),
                        ('active', '=', True),
                        '|',
                        ('style_code', '=ilike', k),
                        ('style_code', '=ilike', f"%{k}%")
                    ], order='id asc')
                    if style_dockets:
                        return self._build_schedule_details_from_dockets(f"Style: {k}", style_dockets)

            # 4. Fourth Priority: Check if search matches a Location (Rack / Bin)
            for k in keys:
                location = StockLocation.search([
                    ('usage', '=', 'internal'),
                    '|', '|',
                    ('name', '=ilike', k),
                    ('name', '=ilike', f"%{k}%"),
                    ('complete_name', '=ilike', f"%{k}%")
                ], limit=1)
                if location:
                    return self._build_location_details(location)

            return {
                'status': 'not_found',
                'search_term': raw,
                'message': _("No Docket, Schedule, Style, or Rack found matching '%s'") % raw
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

        # Force fresh compute of component statuses on docket
        if hasattr(docket, '_compute_component_statuses'):
            try:
                docket._compute_component_statuses()
            except Exception as e:
                _logger.warning("Could not recompute component statuses for %s: %s", getattr(docket, 'name', 'unknown'), str(e))

        # 3. Trims Readiness & Location
        trims_data = self._get_component_info(docket, sched, comp_type='trim')
        has_validated_trims = trims_data['has_validated']
        trims_location = trims_data['location_display']
        trims_parcels = trims_data.get('parcels', [])

        trims_status = docket.trims_status or (sched.trims_status if sched else 'pending')
        carrier_docket_name = docket.trims_issued_with_docket_id.name if docket.trims_issued_with_docket_id else ''
        if not carrier_docket_name and sched and sched.first_issued_docket_id:
            carrier_docket_name = sched.first_issued_docket_id.name
        trims_issued_date = fields.Datetime.to_string(sched.trims_issued_date) if sched and sched.trims_issued_date else ''

        # Trims is ready if in store (ok), already issued, carrier docket, validated receipt exists, or delivery is done
        is_trims_ready = (
            trims_status in ('ok', 'issued', 'already_issued', 'ready')
            or has_validated_trims
            or (docket.delivery_status == 'done')
        )

        trims_info = {
            'status': trims_status,
            'is_ready': is_trims_ready,
            'is_in_store': trims_status == 'ok' or (has_validated_trims and trims_status != 'already_issued'),
            'is_carrier': docket.trims_status == 'issued',
            'is_already_issued': docket.trims_status == 'already_issued',
            'carrier_docket': carrier_docket_name,
            'issued_date': trims_issued_date,
            'location_name': trims_location,
            'parcels': trims_parcels,
        }

        # 4. Embellishment (EMB) Pool & Status
        is_emb = (getattr(docket, 'style_type', '') == 'emb')
        emb_pool_balance = float(getattr(sched, 'remaining_emb_balance', 0.0) if sched else 0.0)
        emb_pool_received = float(getattr(sched, 'total_emb_received_qty', 0.0) if sched else 0.0)
        emb_status = docket.emb_status or (getattr(sched, 'emb_status', 'pending') if sched else 'pending')

        emb_data = self._get_component_info(docket, sched, comp_type='emb') if is_emb else {'has_validated': False, 'location_display': 'Not Assigned', 'parcels': []}
        has_validated_emb = emb_data['has_validated']
        emb_location = emb_data['location_display']
        emb_parcels = emb_data.get('parcels', [])

        req_emb_qty = float(getattr(docket, 'docket_qty', 0.0) or getattr(docket, 'co_qty', 0.0) or 0.0)

        # If schedule pool balance is 0 but direct validated receipt exists for this docket
        if has_validated_emb and emb_pool_balance == 0.0 and req_emb_qty > 0.0:
            emb_pool_balance = req_emb_qty
            emb_pool_received = req_emb_qty

        bal_after = emb_pool_balance - req_emb_qty if getattr(docket, 'delivery_status', 'pending') != 'done' else emb_pool_balance
        is_sufficient = (emb_pool_balance >= req_emb_qty) or (getattr(docket, 'delivery_status', 'pending') == 'done') or has_validated_emb

        is_emb_ready = (
            (not is_emb)
            or (emb_status in ('ok', 'ready', 'issued'))
            or (getattr(docket, 'delivery_status', 'pending') == 'done')
            or has_validated_emb
            or (emb_pool_balance >= req_emb_qty and (emb_pool_balance > 0 or req_emb_qty == 0))
        )

        emb_info = {
            'is_emb_style': is_emb,
            'status': emb_status,
            'is_ready': is_emb_ready,
            'req_qty': int(req_emb_qty),
            'pool_balance': int(emb_pool_balance),
            'pool_received': int(emb_pool_received),
            'balance_after_dispatch': int(bal_after),
            'is_sufficient': is_sufficient,
            'shortage_qty': int(max(0.0, req_emb_qty - emb_pool_balance)) if not is_sufficient else 0,
            'is_delivered': getattr(docket, 'delivery_status', 'pending') == 'done',
            'location_name': emb_location,
            'parcels': emb_parcels,
        }

        # Check pending items for this docket
        pending_items = []
        if not parcels_data:
            pending_items.append("Cut Parcels")
        if not trims_info['is_ready']:
            pending_items.append("Trims")
        if is_emb and not emb_info['is_ready']:
            pending_items.append("Embellishment")

        # 5. Master Dispatch Decision (Traffic Light)
        if getattr(docket, 'delivery_status', 'pending') == 'done':
            decision = {
                'can_issue': False,
                'state': 'already_dispatched',
                'color': 'blue',
                'badge_class': 'decision-dispatched bg-primary text-white',
                'banner_title': _("ALREADY DISPATCHED TO SEWING LINE"),
                'banner_subtitle': _("This Docket has already been fully issued and sent out to the sewing floor."),
                'pending_items': [],
            }
        elif pending_items:
            pending_desc = ", ".join(f"{item} Pending" for item in pending_items)
            decision = {
                'can_issue': False,
                'state': 'not_completed',
                'color': 'red',
                'badge_class': 'decision-blocked bg-danger text-white',
                'banner_title': _("DO NOT ISSUE - DOCKET NOT COMPLETED!"),
                'banner_subtitle': _("Pending: %s") % pending_desc,
                'pending_items': [f"{item} Pending" for item in pending_items],
            }
        else:
            decision = {
                'can_issue': True,
                'state': 'ready_to_issue',
                'color': 'green',
                'badge_class': 'decision-ready bg-success text-white',
                'banner_title': _("ALL COMPONENTS READY - CAN ISSUE TO LINE!"),
                'banner_subtitle': _("All Cut Parcels, Trims, and Embellishments are verified and available."),
                'pending_items': [],
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

        dockets = getattr(sched, 'docket_ids', False)
        if dockets:
            dockets = dockets.filtered(lambda d: d.is_docket and d.active)
        if not dockets:
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
            try:
                doc_data = self._build_docket_details(doc)
                dockets_summary.append({
                    'docket_id': doc.id,
                    'docket_no': doc.name,
                    'co_qty': getattr(doc, 'co_qty', 0.0),
                    'module_fr': getattr(doc, 'fr_module', '') or getattr(doc, 'module', '') or '-',
                    'delivery_status': getattr(doc, 'delivery_status', 'pending') or 'pending',
                    'can_issue': doc_data['decision']['can_issue'],
                    'decision': doc_data['decision'],
                    'parcels': doc_data['parcels'],
                    'trims': doc_data['trims'],
                    'emb': doc_data['emb']
                })
            except Exception as e:
                _logger.warning("Error building docket details for %s in schedule %s: %s", getattr(doc, 'name', 'unknown'), getattr(sched, 'name', 'unknown'), str(e))

        # Schedule-level component locations
        sched_trims = self._get_component_info(None, sched, comp_type='trim')
        sched_emb = self._get_component_info(None, sched, comp_type='emb')

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
                'trims_location': sched_trims['location_display'],
                'emb_pool_balance': getattr(sched, 'remaining_emb_balance', 0.0),
                'emb_pool_received': getattr(sched, 'total_emb_received_qty', 0.0),
                'emb_location': sched_emb['location_display'],
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
            try:
                doc_data = self._build_docket_details(doc)
                dockets_summary.append({
                    'docket_id': doc.id,
                    'docket_no': doc.name,
                    'co_qty': getattr(doc, 'co_qty', 0.0),
                    'module_fr': getattr(doc, 'fr_module', '') or getattr(doc, 'module', '') or '-',
                    'delivery_status': getattr(doc, 'delivery_status', 'pending') or 'pending',
                    'can_issue': doc_data['decision']['can_issue'],
                    'decision': doc_data['decision'],
                    'parcels': doc_data['parcels'],
                    'trims': doc_data['trims'],
                    'emb': doc_data['emb']
                })
            except Exception as e:
                _logger.warning("Error building docket details for %s in schedule %s: %s", getattr(doc, 'name', 'unknown'), sched_name, str(e))

        first_trims = self._get_component_info(first_doc, None, comp_type='trim')
        first_emb = self._get_component_info(first_doc, None, comp_type='emb')

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
                'trims_location': first_trims['location_display'],
                'emb_pool_balance': 0.0,
                'emb_pool_received': 0.0,
                'emb_location': first_emb['location_display'],
                'total_dockets_count': len(dockets_summary),
                'ready_dockets_count': len([d for d in dockets_summary if d['can_issue']]),
            },
            'dockets': dockets_summary
        }

    @api.model
    def _build_location_details(self, location):
        """Returns all items currently stored in a given Rack/Bin location (Cut Panels + Component Receipts)"""
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

        # Direct SQL search for Component Receipt parcel lines stored in this location
        try:
            sql_loc_comps = """
                SELECT 
                    bcrl.id as line_id,
                    bcrl.parcel_no,
                    bcrl.barcode,
                    bcr.id as receipt_id,
                    bcr.name as receipt_name,
                    bcr.component_type,
                    bcr.style_code,
                    bcr.color_name,
                    pt.name as docket_name,
                    bsm.name as schedule_name
                FROM brandix_component_receipt_line bcrl
                JOIN brandix_component_receipt bcr ON bcrl.receipt_id = bcr.id
                LEFT JOIN product_template pt ON bcr.docket_id = pt.id
                LEFT JOIN brandix_schedule_master bsm ON bcr.schedule_master_id = bsm.id
                WHERE bcrl.location_id = %s
                  AND bcr.state = 'validated'
                ORDER BY bcr.id DESC, bcrl.parcel_no ASC
            """
            with self.env.cr.savepoint():
                self.env.cr.execute(sql_loc_comps, (location.id,))
                rows_cl = self.env.cr.dictfetchall()
            for cl in rows_cl:
                comp_type_label = 'TRIMS' if cl.get('component_type') == 'trim' else 'EMB'
                d_name = cl.get('docket_name') or cl.get('barcode') or '-'
                s_name = cl.get('schedule_name') or '-'
                stored_items.append({
                    'parcel_id': cl.get('line_id'),
                    'parcel_name': f"[{comp_type_label}] Parcel #{cl.get('parcel_no')} ({cl.get('receipt_name')})",
                    'parcel_number': cl.get('parcel_no'),
                    'docket_no': d_name,
                    'schedule_no': s_name,
                    'style_code': cl.get('style_code') or '-',
                    'color_name': cl.get('color_name') or '-',
                    'module_fr': '-',
                    'grn_name': cl.get('receipt_name'),
                    'history_count': 0
                })
        except Exception as e:
            _logger.exception("Error fetching location component lines for %s: %s", location.name, str(e))

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
    def _get_component_info(self, docket, sched, comp_type='trim'):
        """
        Retrieves receipt state and physical bin/rack storage location for Trims or Embellishments.
        Uses direct database SQL queries combined with ORM fallbacks to guarantee 100% accurate location data.
        """
        try:
            docket_id = docket.id if docket else 0
            docket_name = docket.name.strip() if docket and docket.name else ''
            docket_num = getattr(docket, 'docket_number', '') or ''
            docket_num = docket_num.strip() if docket_num else ''

            sched_ids = set()
            sched_names = set()

            if sched and sched.id:
                sched_ids.add(sched.id)
                if getattr(sched, 'name', None):
                    sched_names.add(sched.name.strip())

            if docket:
                if hasattr(docket, 'schedule_master_ids') and docket.schedule_master_ids:
                    for s in docket.schedule_master_ids:
                        sched_ids.add(s.id)
                        if s.name:
                            sched_names.add(s.name.strip())
                if hasattr(docket, 'schedule_master_id') and docket.schedule_master_id:
                    sched_ids.add(docket.schedule_master_id.id)
                    if docket.schedule_master_id.name:
                        sched_names.add(docket.schedule_master_id.name.strip())
                if docket.schedule_no:
                    for s in str(docket.schedule_no).replace(';', ',').split(','):
                        clean_s = s.strip()
                        if clean_s:
                            sched_names.add(clean_s)

            sched_id_list = list(sched_ids) or [0]
            sched_name_list = list(sched_names) or ['']

            barcode_patterns = set()
            if docket_name:
                barcode_patterns.add(docket_name)
                if ':' in docket_name:
                    barcode_patterns.add(docket_name.split(':')[-1].strip())
            if docket_num:
                barcode_patterns.add(docket_num)
            for sn in sched_names:
                if sn:
                    barcode_patterns.add(sn)

            locations = []
            has_validated = False
            parcels_info = []

            # 1. Safely check if relation tables exist
            has_rel_docket = False
            has_rel_sched = False
            try:
                with self.env.cr.savepoint():
                    self.env.cr.execute("SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'component_receipt_docket_rel' LIMIT 1")
                    has_rel_docket = bool(self.env.cr.fetchone())
            except Exception:
                has_rel_docket = False

            try:
                with self.env.cr.savepoint():
                    self.env.cr.execute("SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'component_receipt_schedule_rel' LIMIT 1")
                    has_rel_sched = bool(self.env.cr.fetchone())
            except Exception:
                has_rel_sched = False

            # Direct SQL on brandix_component_receipt_line joined with brandix_component_receipt and stock_location
            exact_barcodes = list(barcode_patterns) or ['']
            ilike_barcodes = [f"%{b}%" for b in barcode_patterns if b] or ['%NONE%']
            exact_sched_names = sched_name_list
            ilike_sched_names = [f"%{s}%" for s in sched_name_list if s] or ['%NONE%']

            where_clauses = [
                "bcrl.barcode = ANY(%s)",
                "bcrl.barcode ILIKE ANY(%s)",
                "(bcr.docket_id IS NOT NULL AND bcr.docket_id = %s)",
                "(bcr.schedule_master_id IS NOT NULL AND bcr.schedule_master_id = ANY(%s))",
                "(bcr.schedule_master_id IS NOT NULL AND bcr.schedule_master_id IN (SELECT id FROM brandix_schedule_master WHERE name = ANY(%s) OR name ILIKE ANY(%s)))"
            ]
            params = [
                comp_type,
                exact_barcodes,
                ilike_barcodes,
                docket_id,
                sched_id_list,
                exact_sched_names,
                ilike_sched_names
            ]

            if has_rel_docket and docket_id:
                where_clauses.append("(bcr.id IN (SELECT receipt_id FROM component_receipt_docket_rel WHERE docket_id = %s))")
                params.append(docket_id)

            if has_rel_sched and sched_id_list and sched_id_list != [0]:
                where_clauses.append("(bcr.id IN (SELECT receipt_id FROM component_receipt_schedule_rel WHERE schedule_id = ANY(%s)))")
                params.append(sched_id_list)

            sql = f"""
                SELECT DISTINCT
                    sl.id as location_id,
                    sl.name as location_name,
                    sl.complete_name as location_complete_name,
                    bcr.id as receipt_id,
                    bcr.name as receipt_name,
                    bcrl.id as line_id,
                    bcrl.parcel_no,
                    bcrl.barcode
                FROM brandix_component_receipt_line bcrl
                JOIN brandix_component_receipt bcr ON bcrl.receipt_id = bcr.id
                JOIN stock_location sl ON bcrl.location_id = sl.id
                WHERE bcr.state = 'validated'
                  AND bcr.component_type = %s
                  AND (
                      {' OR '.join(where_clauses)}
                  )
                ORDER BY bcr.id DESC, bcrl.parcel_no ASC
            """

            rows = []
            with self.env.cr.savepoint():
                self.env.cr.execute(sql, tuple(params))
                rows = self.env.cr.dictfetchall()

            History = self.env['brandix.docket.parcel.location.history'].sudo() if 'brandix.docket.parcel.location.history' in self.env else None

            for r in rows:
                has_validated = True
                loc = r.get('location_name') or r.get('location_complete_name')
                if loc and loc not in locations:
                    locations.append(loc)
                line_id = r.get('line_id')
                hist_count = History.search_count([('component_receipt_line_id', '=', line_id)]) if (History and line_id) else 0
                parcels_info.append({
                    'id': line_id,
                    'parcel_number': r.get('parcel_no'),
                    'parcel_name': f"{'Trims' if comp_type == 'trim' else 'EMB'} Parcel #{r.get('parcel_no')}",
                    'location_id': r.get('location_id'),
                    'location_name': r.get('location_name') or 'UNASSIGNED',
                    'location_full_name': r.get('location_complete_name') or 'Not Placed Yet',
                    'receipt_name': r.get('receipt_name'),
                    'comp_type': comp_type,
                    'history_count': hist_count,
                })

            # 2. Check if receipts exist with non-empty location_summary
            if not locations:
                sum_where = [
                    "(bcr.docket_id IS NOT NULL AND bcr.docket_id = %s)",
                    "(bcr.schedule_master_id IS NOT NULL AND bcr.schedule_master_id = ANY(%s))",
                    "(bcr.id IN (SELECT receipt_id FROM brandix_component_receipt_line WHERE barcode = ANY(%s) OR barcode ILIKE ANY(%s)))"
                ]
                sum_params = [comp_type, docket_id, sched_id_list, exact_barcodes, ilike_barcodes]
                if has_rel_docket and docket_id:
                    sum_where.append("(bcr.id IN (SELECT receipt_id FROM component_receipt_docket_rel WHERE docket_id = %s))")
                    sum_params.append(docket_id)
                if has_rel_sched and sched_id_list and sched_id_list != [0]:
                    sum_where.append("(bcr.id IN (SELECT receipt_id FROM component_receipt_schedule_rel WHERE schedule_id = ANY(%s)))")
                    sum_params.append(sched_id_list)

                sql_summary = f"""
                    SELECT DISTINCT bcr.location_summary
                    FROM brandix_component_receipt bcr
                    WHERE bcr.state = 'validated'
                      AND bcr.component_type = %s
                      AND (
                          {' OR '.join(sum_where)}
                      )
                      AND bcr.location_summary IS NOT NULL
                      AND bcr.location_summary != '-'
                """
                with self.env.cr.savepoint():
                    self.env.cr.execute(sql_summary, tuple(sum_params))
                    for srow in self.env.cr.dictfetchall():
                        has_validated = True
                        summary = srow.get('location_summary')
                        if summary:
                            for p in summary.split(','):
                                cp = p.strip()
                                if cp and cp not in locations:
                                    locations.append(cp)

            # 3. Check if receipt exists at all
            if not has_validated:
                chk_where = [
                    "(bcr.docket_id IS NOT NULL AND bcr.docket_id = %s)",
                    "(bcr.schedule_master_id IS NOT NULL AND bcr.schedule_master_id = ANY(%s))",
                    "(bcr.id IN (SELECT receipt_id FROM brandix_component_receipt_line WHERE barcode = ANY(%s) OR barcode ILIKE ANY(%s)))"
                ]
                chk_params = [comp_type, docket_id, sched_id_list, exact_barcodes, ilike_barcodes]
                if has_rel_docket and docket_id:
                    chk_where.append("(bcr.id IN (SELECT receipt_id FROM component_receipt_docket_rel WHERE docket_id = %s))")
                    chk_params.append(docket_id)
                if has_rel_sched and sched_id_list and sched_id_list != [0]:
                    chk_where.append("(bcr.id IN (SELECT receipt_id FROM component_receipt_schedule_rel WHERE schedule_id = ANY(%s)))")
                    chk_params.append(sched_id_list)

                sql_check = f"""
                    SELECT bcr.id
                    FROM brandix_component_receipt bcr
                    WHERE bcr.state = 'validated'
                      AND bcr.component_type = %s
                      AND (
                          {' OR '.join(chk_where)}
                      )
                    LIMIT 1
                """
                with self.env.cr.savepoint():
                    self.env.cr.execute(sql_check, tuple(chk_params))
                    if self.env.cr.fetchone():
                        has_validated = True

            if locations:
                location_display = ", ".join(locations)
            elif has_validated:
                location_display = 'In Store'
            else:
                location_display = 'Not Assigned'

            return {
                'has_validated': has_validated,
                'location_display': location_display,
                'parcels': parcels_info
            }
        except Exception as e:
            _logger.exception("Database error getting component info for docket %s: %s", getattr(docket, 'name', 'unknown'), str(e))
            return {'has_validated': False, 'location_display': 'Not Assigned', 'parcels': []}

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

                # Count component parcels in this location
                comp_count = 0
                try:
                    with self.env.cr.savepoint():
                        self.env.cr.execute("""
                            SELECT COUNT(*) FROM brandix_component_receipt_line bcrl
                            JOIN brandix_component_receipt bcr ON bcrl.receipt_id = bcr.id
                            WHERE bcrl.location_id = %s AND bcr.state = 'validated'
                        """, (loc.id,))
                        comp_count = self.env.cr.fetchone()[0] or 0
                except Exception:
                    comp_count = 0

                racks.append({
                    'id': loc.id,
                    'name': loc.name,
                    'complete_name': loc.complete_name,
                    'active_parcel_count': count + comp_count,
                    'done_parcel_count': done_count,
                    'total_count': count + done_count + comp_count
                })

            return racks
        except Exception as e:
            _logger.exception("Error in get_warehouse_racks_overview: %s", str(e))
            return []

    @api.model
    def get_parcel_location_history(self, parcel_location_id, parcel_type='cut'):
        """Returns the full audit trail of location movements for a parcel (cut, trim, or emb)"""
        try:
            History = self.env['brandix.docket.parcel.location.history'].sudo()
            if parcel_type in ('trim', 'emb'):
                domain = [('component_receipt_line_id', '=', int(parcel_location_id))]
            else:
                domain = [('parcel_location_id', '=', int(parcel_location_id))]

            logs = History.search(domain, order='change_date desc, id desc')

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
    def reassign_parcel_location(self, parcel_location_id, new_location_id, reason="Manual Smart Board Reassignment", parcel_type='cut'):
        """Directly relocates a parcel (cut, trim, or emb) from the Smart Board and logs audit trail"""
        try:
            Location = self.env['stock.location'].sudo()
            target_loc = Location.browse(int(new_location_id))
            if not target_loc.exists():
                return {'success': False, 'message': 'Target Location not found'}

            if parcel_type in ('trim', 'emb'):
                CompLine = self.env['brandix.component.receipt.line'].sudo()
                parcel = CompLine.browse(int(parcel_location_id))
                if not parcel.exists():
                    return {'success': False, 'message': 'Component parcel not found'}

                parcel.with_context(location_change_reason=reason).write({
                    'location_id': int(new_location_id)
                })
                new_name = parcel.location_id.name
                new_full_name = parcel.location_id.complete_name
            else:
                ParcelLoc = self.env['brandix.docket.parcel.location'].sudo()
                parcel = ParcelLoc.browse(int(parcel_location_id))
                if not parcel.exists():
                    return {'success': False, 'message': 'Parcel not found'}

                parcel.with_context(location_change_reason=reason).write({
                    'location_dest_id': int(new_location_id)
                })
                new_name = parcel.location_dest_id.name
                new_full_name = parcel.location_dest_id.complete_name

            return {
                'success': True,
                'new_location_name': new_name,
                'location_name': new_name,
                'location_full_name': new_full_name
            }
        except Exception as e:
            _logger.exception("Error in reassign_parcel_location: %s", str(e))
            return {'success': False, 'message': str(e)}
