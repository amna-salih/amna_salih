# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015-Today ODOOTECH FZE (<http://www.odootech-fze.com>)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>
#ensure_one
##############################################################################
from odoo import _, api, fields, models
from odoo.exceptions import UserError
import math
from dateutil.relativedelta import relativedelta
from random import randint

from odoo import api, Command, fields, models, tools, _
from odoo.addons.iap.tools import iap_tools
from odoo.osv import expression
from odoo.exceptions import AccessError
from werkzeug.urls import url_encode

TICKET_PRIORITY = [
    ('1', 'Low priority'),
    ('2', 'Medium High'),
    ('3', 'High High'),
]


class HdTeam(models.Model):
    _name = "hd.team"
    _description = "Help Desk Team"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    
    name = fields.Char(string="Team")

class HelpdeskTag(models.Model):
    _name = 'helpdesk.tag'
    _description = 'Helpdesk Tags'
    _order = 'name'

    def _get_default_color(self):
        return randint(1, 11)

    name = fields.Char(required=True, translate=True)
    color = fields.Integer('Color', default=_get_default_color)

    _sql_constraints = [
        ('name_uniq', 'unique (name)', "Tag name already exists !"),
    ]


    
class HdTicket(models.Model):
    _name = "hd.ticket"
    _description = "Help Desk Ticket"
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin', 'utm.mixin']
    _order = "id desc"


    def _get_default_requested_by(self):
        return self.env["res.users"].browse(self.env.uid)
    
    name = fields.Char(string="Ticket Reference",readonly="1")
    ticket_name = fields.Char(string="Ticket")
    time_submitted = fields.Date("Time submitted", readonly=True, default=fields.Datetime.now)
    description = fields.Html(string="Description", required=True)
    team_id = fields.Many2one('hd.team', string='Helpdesk Team', index=True, required=True)
    user_id = fields.Many2one(
        'res.users', string='Assigned to', store=True,
        readonly=False, default=_get_default_requested_by, tracking=True)
    priority = fields.Selection(TICKET_PRIORITY, string='Priority', default='1')
    partner_id = fields.Many2one(
        'res.partner', string='Customer', readonly=True,
        states={'draft': [('readonly', False)]},
        required=True, change_default=True, index=True, tracking=1 )
    partner_phone = fields.Char(related="partner_id.phone",  string="Customer Phone")
    partner_email = fields.Char(related="partner_id.email",  string="Customer Email")
    state = fields.Selection([
        ('draft', 'New'),
        ('confirm', 'In Progress'),
        ('done', 'Solved'),
        ('Cancel', 'Canceled'),
    ], store=True, default='draft')
    hosting_type = fields.Selection([
        ('on-premise', 'on-premise'),
        ('Cloud', 'Cloud'),
    ], store=True, required=True)
    tag_ids = fields.Many2many('helpdesk.tag', string='Tags')
    close_date = fields.Date("Close date", copy=False)
    resolution_time = fields.Integer("Resolution time", compute='_compute_close_hours', store=True,
                                 help="This duration is based on the working calendar of the team")

    @api.depends('create_date', 'close_date')
    def _compute_close_hours(self):
        for ticket in self:
            if ticket.close_date:
                ticket.resolution_time = ticket.close_date - ticket.time_submitted
            else:
                ticket.resolution_time = False

    def unlink(self):
        for ticket in self:
            if ticket.state != 'draft':
                raise UserError(
                    _("You cannot delete a ticket which is not draft.")
                )
        return super(HdTicket, self).unlink()

    def button_draft(self):

        self.write({"state": 'confirm'})

    def button_confirm(self):
        self.write({"state": "done" ,"close_date": fields.Date.today()})


    def button_cancel(self):
        return self.write({"state": "Cancel"})

    def button_set_draft(self):
        return self.write({"state": "draft"})

    @api.model
    def create(self, vals):
        res = super(HdTicket, self).create(vals)
        next_seq = self.env['ir.sequence'].get('hd.ticket')
        res.update({'name': next_seq})
        return res

    def _compute_access_url(self):

        super(HdTicket, self)._compute_access_url()
        for ticket in self:
            ticket.access_url = '/my/tickets/%s' % (ticket.id)

    def preview_ticket(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'target': 'self',
            'url': self.get_portal_url(),
        }

    def _get_portal_return_action(self):
        """ Return the action used to display ticket when returning from customer portal. """
        self.ensure_one()
        return self.env.ref('amna_salih.ticket_action')

    def has_to_be_signed(self, include_draft=False):
        return True


    def _get_share_url(self, redirect=False, signup_partner=False, pid=None):
        """Override for sales order.

        If the ticket is in a state where an action is required from the partner,
        return the URL with a login token. Otherwise, return the URL with a
        generic access token (no login).
        """
        self.ensure_one()
        if self.state != 'done':
            auth_param = url_encode(
                self.partner_id.signup_get_auth_param()[self.partner_id.id])
            return self.get_portal_url(query_string='&%s' % auth_param)
        return super(HdTicket, self)._get_share_url(redirect, signup_partner, pid)

class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _compute_ticket_count(self):
        for record in self:
            tickets = record.env['hd.ticket'].sudo().search([('partner_id', '=', record.id)])
            record.tickets_count = len(tickets)

    tickets_count = fields.Integer(compute='_compute_ticket_count', string='Tickets', default=0)

class ResUsers(models.Model):
    _inherit = 'res.users'

    def _compute_ticket_count(self):
        for record in self:
            tickets = record.env['hd.ticket'].sudo().search([('user_id', '=', record.id)])
            record.tickets_count = len(tickets)

    tickets_count = fields.Integer(compute='_compute_ticket_count', string='Tickets', default=0)


