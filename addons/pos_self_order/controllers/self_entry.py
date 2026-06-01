# -*- coding: utf-8 -*-
import werkzeug

from odoo import http
from odoo.http import request


class PosSelfKiosk(http.Controller):
    @http.route(["/pos-self/<config_id>", "/pos-self/<config_id>/<path:subpath>"], auth="public", website=True, sitemap=True)
    def start_self_ordering(self, config_id=None, access_token=None, table_identifier=None, partner_token=None, subpath=None):
        pos_config, _, config_access_token = self._verify_entry_access(config_id, access_token, table_identifier)
        partner = self._get_partner_from_token(pos_config, partner_token)
        preset = self._get_locked_preset_from_partner(pos_config, partner)
        serialized_partner = self._serialize_partner_for_session(partner)
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
                            'locked_partner': serialized_partner,
                        },
                        "base_url": request.env['pos.session'].get_base_url(),
                        "db": request.env.cr.dbname,
                    }
                }
            )

    def _get_locked_preset_from_partner(self, pos_config, partner):
        preset = partner.self_order_preset_id
        if not preset:
            raise werkzeug.exceptions.NotFound()

        allowed_presets = pos_config.available_preset_ids
        if preset not in allowed_presets:
            raise werkzeug.exceptions.NotFound()

        return preset

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

    def _get_partner_from_token(self, pos_config, partner_token):
        if not partner_token:
            raise werkzeug.exceptions.NotFound()

        try:
            partner_id = int(partner_token)
        except (TypeError, ValueError):
            raise werkzeug.exceptions.NotFound()

        partner = pos_config.env['res.partner'].sudo().browse(partner_id)
        if not partner.exists():
            raise werkzeug.exceptions.NotFound()

        return partner

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
