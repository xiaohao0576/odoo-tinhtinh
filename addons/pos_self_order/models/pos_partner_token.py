# Part of Odoo. See LICENSE file for full copyright and licensing details.

import secrets

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PosPartnerToken(models.Model):
    _name = "pos.partner.token"
    _description = "POS Partner Access Token"
    _inherit = ["mail.thread"]

    name = fields.Char(required=True, tracking=True)
    token_hash = fields.Char(
        required=True,
        index=True,
        copy=False,
        tracking=True,
        default=lambda self: self._generate_token_hash(),
    )
    partner_id = fields.Many2one("res.partner", required=True, tracking=True)
    config_id = fields.Many2one("pos.config", required=True, tracking=True)
    preset_id = fields.Many2one("pos.preset", required=True, tracking=True)
    pricelist_id = fields.Many2one(
        "product.pricelist",
        related="preset_id.pricelist_id",
        readonly=True,
        store=True,
    )
    printer_id = fields.Many2one("pos.printer", required=True, tracking=True)
    telegram_username = fields.Char(
        string="Telegram Username",
        tracking=True,
        help="Customer support Telegram username without @.",
    )
    telegram_prefill_text = fields.Text(
        string="Telegram Prefill Template",
        tracking=True,
        help="Template for Telegram deeplink prefill text. Variables are resolved at runtime.",
    )
    active = fields.Boolean(default=True, tracking=True)
    expires_at = fields.Datetime(tracking=True)
    last_used_at = fields.Datetime(readonly=True)
    last_access_ip = fields.Char(readonly=True, tracking=True)
    use_count = fields.Integer(default=0, readonly=True)

    _sql_constraints = [
        ("token_hash_unique", "unique(token_hash)", "Token hash must be unique."),
    ]

    @api.model
    def _generate_token_hash(self):
        token = secrets.token_urlsafe(24)
        while self.search_count([("token_hash", "=", token)]):
            token = secrets.token_urlsafe(24)
        return token

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault("token_hash", self._generate_token_hash())
            config_id = vals.get("config_id")
            if config_id and not vals.get("printer_id"):
                config = self.env["pos.config"].browse(config_id)
                vals["printer_id"] = config.default_receipt_printer_id.id
        return super().create(vals_list)

    @api.constrains("preset_id", "config_id")
    def _check_preset_allowed_in_config(self):
        for record in self:
            if record.preset_id not in record.config_id.available_preset_ids:
                raise ValidationError(
                    _("The selected preset is not available in the selected Point of Sale.")
                )

    @api.onchange("config_id")
    def _onchange_config_id(self):
        if self.config_id and not self.printer_id:
            self.printer_id = self.config_id.default_receipt_printer_id

    def action_regenerate_token_hash(self):
        for record in self:
            record.token_hash = record._generate_token_hash()