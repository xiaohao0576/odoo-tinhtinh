# -*- coding: utf-8 -*-
import werkzeug

from odoo import fields, http
from odoo.http import request


class PosSelfKiosk(http.Controller):
    @http.route(["/pos-self/<config_id>", "/pos-self/<config_id>/<path:subpath>"], auth="public", website=True, sitemap=True)
    def start_self_ordering(self, config_id=None, access_token=None, table_identifier=None, partner_token=None, subpath=None):
        try:
            pos_config, _, config_access_token = self._verify_entry_access(config_id, access_token, table_identifier)
            partner_token_record = self._get_partner_token_record(pos_config, partner_token)
            partner = partner_token_record.partner_id
            preset = partner_token_record.preset_id
            printer = partner_token_record.printer_id
            language = partner_token_record.default_language_id
            self._mark_partner_token_used(partner_token_record)
            serialized_partner = self._serialize_partner_for_session(partner)
            serialized_printer = self._serialize_printer_for_session(printer)
            return request.render(
                    'pos_self_order.index',
                    {
                        'access_token': config_access_token,
                        'session_info': {
                            **request.env["ir.http"].get_frontend_session_info(),
                            'currencies': request.env["res.currency"].get_all_currencies(),
                            'data': {
                                'config_id': pos_config.id,
                                'self_ordering_mode': pos_config.self_ordering_mode,
                                'locked_partner_id': partner.id,
                                'locked_preset_id': preset.id,
                                'locked_printer_id': printer.id,
                                'locked_language_id': language.id if language else False,
                                'locked_language_code': language.code if language else False,
                                'locked_partner': serialized_partner,
                                'locked_printer': serialized_printer,
                            },
                            "base_url": request.env['pos.session'].get_base_url(),
                            "db": request.env.cr.dbname,
                        }
                    }
                )
        except werkzeug.exceptions.NotFound:
            return self._render_friendly_not_found()

    def _render_friendly_not_found(self):
        lang = request.lang or request.cookies.get("frontend_lang") or "en_US"
        response = request.render("pos_self_order.friendly_not_found", {
            "is_zh": str(lang).startswith("zh"),
        })
        response.status_code = 404
        return response

    def _serialize_partner_for_session(self, partner):
        return {
            'id': partner.id,
            'name': partner.name,
            'email': partner.email,
            'phone': partner.phone,
            'street': partner.street,
            'city': partner.city,
            'zip': partner.zip,
            'country_id': partner.country_id.id if partner.country_id else False,
            'state_id': partner.state_id.id if partner.state_id else False,
            'write_date': str(partner.write_date) if partner.write_date else False,
            'property_product_pricelist': partner.property_product_pricelist.id if partner.property_product_pricelist else False,
        }

    def _serialize_printer_for_session(self, printer):
        return {
            'id': printer.id,
            'name': printer.name,
            'product_categories_ids': printer.product_categories_ids.ids,
            'printer_type': printer.printer_type,
            'use_type': printer.use_type,
            'use_lna': printer.use_lna,
            'printer_ip': printer.printer_ip,
            'paper_size': printer.paper_size,
            'timeout': printer.timeout,
        }

    def _get_partner_token_record(self, pos_config, partner_token):
        if not partner_token:
            raise werkzeug.exceptions.NotFound()

        token_record = request.env['pos.partner.token'].sudo().search([
            ('token_hash', '=', partner_token),
            ('active', '=', True),
            ('config_id', '=', pos_config.id),
        ], limit=1)

        if not token_record:
            raise werkzeug.exceptions.NotFound()

        if token_record.expires_at and token_record.expires_at <= fields.Datetime.now():
            raise werkzeug.exceptions.NotFound()

        if token_record.preset_id not in pos_config.available_preset_ids:
            raise werkzeug.exceptions.NotFound()

        return token_record

    def _mark_partner_token_used(self, token_record):
        token_record.sudo().write({
            'last_used_at': fields.Datetime.now(),
            'last_access_ip': self._get_client_ip(),
            'use_count': token_record.use_count + 1,
        })

    def _get_client_ip(self):
        forwarded_for = request.httprequest.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        return request.httprequest.remote_addr or ''

    @http.route("/pos-self/data/<config_id>", type='jsonrpc', auth='public', website=True)
    def get_self_ordering_data(self, config_id=None, access_token=None, table_identifier=None):
        pos_config, _, config_access_token = self._verify_entry_access(config_id, access_token, table_identifier)
        data = pos_config.load_self_data()
        data['pos.config'][0]['access_token'] = config_access_token
        return data

    @http.route("/pos-self/receipt-template/<config_id>", type='jsonrpc', auth='public')
    def get_self_ordering_receipt_template(self, config_id=None, access_token=None, table_identifier=None):
        pos_config, _, _ = self._verify_entry_access(config_id, access_token, table_identifier)
        return pos_config.env['pos.order'].get_receipt_template_for_pos_frontend()

    @http.route("/pos-self/relations/<config_id>", type='jsonrpc', auth='public')
    def get_self_ordering_relations(self, config_id=None, access_token=None, table_identifier=None):
        pos_config, _, _ = self._verify_entry_access(config_id, access_token, table_identifier)
        return pos_config.load_data_params()

    def _verify_entry_access(self, config_id=None, access_token=None, table_identifier=None):
        table_sudo = False

        if not config_id or not config_id.isnumeric():
            raise werkzeug.exceptions.NotFound()

        if access_token:
            config_access_token = True
            pos_config_sudo = request.env["pos.config"].sudo().search([
                ("id", "=", config_id), ('access_token', '=', access_token)], limit=1)
        else:
            config_access_token = False
            pos_config_sudo = request.env["pos.config"].sudo().search([
                ("id", "=", config_id)], limit=1)

        if not pos_config_sudo or pos_config_sudo.self_ordering_mode == 'nothing':
            raise werkzeug.exceptions.NotFound()

        company = pos_config_sudo.company_id
        user = pos_config_sudo.self_ordering_default_user_id
        pos_config = pos_config_sudo.sudo(False).with_company(company).with_user(user).with_context(allowed_company_ids=company.ids, lang=request.cookies.get('frontend_lang'))

        if not pos_config:
            raise werkzeug.exceptions.NotFound()

        if pos_config and pos_config.has_active_session and pos_config.self_ordering_mode == 'mobile':
            if config_access_token:
                config_access_token = pos_config.access_token
            table_sudo = table_identifier and (
                request.env["restaurant.table"]
                .sudo()
                .search([("identifier", "=", table_identifier), ("active", "=", True)], limit=1)
            )
            if table_sudo and table_sudo.parent_id:
                table_sudo = table_sudo.parent_id
        elif pos_config.self_ordering_mode == 'kiosk':
            if config_access_token:
                config_access_token = pos_config.access_token
        else:
            config_access_token = ''

        table = table_sudo.sudo(False).with_company(company).with_user(user) if table_sudo else False
        return pos_config, table, config_access_token
