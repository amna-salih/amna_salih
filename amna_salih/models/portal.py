# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
print("AMNA****************************************")
import binascii

from odoo import fields, http, _
from odoo.exceptions import AccessError, MissingError
from odoo.http import request
from odoo.addons.portal.controllers.mail import _message_post_helper
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager, get_records_pager
from odoo.osv import expression


class CustomerPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        print("_prepare_home_portal_values")
        values = super()._prepare_home_portal_values(counters)
        if 'ticket_count' in counters:
            ticket_count = request.env['hd.ticket'].search_count([]) if request.env['hd.ticket'].check_access_rights('read', raise_exception=False) else 0
            values['ticket_count'] = ticket_count
        return values


    def _ticket_get_page_view_values(self, ticket, access_token, **kwargs):
        print("ggggggggggggggggggggggggg_values")
        values = {
            'hd_ticket': ticket,
            'token': access_token,
            'bootstrap_formatting': True,
            'partner_id': ticket.partner_id.id,
            'report_type': 'html',
            'action': ticket._get_portal_return_action(),
        }

        history = request.session.get('my_tickets_history', [])

        values.update(get_records_pager(history, ticket))

        return values



    @http.route(['/my/tickets', '/my/tickets/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_tickets(self, page=1, date_begin=None, date_end=None, sortby=None, **kw):
        print("portal_my_tickets")
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        HdTicket = request.env['hd.ticket']

        domain = []

        searchbar_sortings = {
            'date': {'label': _('Ticket Date'), 'ticket': 'time_submitted desc'},
            'name': {'label': _('Reference'), 'ticket': 'name'},
            'stage': {'label': _('Stage'), 'ticket': 'state'},
        }
        # default sortby offer
        if not sortby:
            sortby = 'date'
        sort_ticket = searchbar_sortings[sortby]['ticket']


        if date_begin and date_end:
            domain += [('create_date', '>', date_begin), ('create_date', '<=', date_end)]

        # count for pager
        ticket_count = HdTicket.search_count(domain)
        # pager
        pager = portal_pager(
            url="/my/tickets",
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby},
            total=ticket_count,
            page=page,
            step=self._items_per_page
        )
        # content according to pager
        tickets = HdTicket.search(domain, order=sort_ticket, limit=self._items_per_page, offset=pager['offset'])
        request.session['my_tickets_history'] = tickets.ids[:100]

        values.update({
            'date': date_begin,
            'tickets': tickets.sudo(),
            'page_name': 'ticket',
            'pager': pager,
            'default_url': '/my/tickets',
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
        })
        return request.render("amna_salih.portal_my_tickets", values)




    @http.route(['/my/tickets/<int:ticket_id>'], type='http', auth="public", website=True)
    def portal_ticket_page(self, ticket_id, report_type=None, access_token=None, message=False, download=False, **kw):
        print("aaaaaaaaaaaaaaaaaaaaaa************")
        try:
            ticket_sudo = self._document_check_access('hd.ticket', ticket_id, access_token=access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')

        # if report_type in ('html', 'pdf', 'text'):
        #     return self._show_report(model=ticket_sudo, report_type=report_type, report_ref='amna_salih.action_report_ticket', download=download)


        if ticket_sudo:
            # store the date as a string in the session to allow serialization
            now = fields.Date.today().isoformat()
            session_obj_date = request.session.get('view_quote_%s' % ticket_sudo.id)
            if session_obj_date != now and request.env.user.share and access_token:
                request.session['view_quote_%s' % ticket_sudo.id] = now
                body = _('ticket viewed by customer %s', ticket_sudo.partner_id.name)
                _message_post_helper(
                    "hd.ticket",
                    ticket_sudo.id,
                    body,
                    token=ticket_sudo.access_token,
                    message_type="notification",
                    subtype_xmlid="mail.mt_note",
                    partner_ids=ticket_sudo.user_id.sudo().partner_id.ids,
                )

        values = self._ticket_get_page_view_values(ticket_sudo, access_token, **kw)
        values['message'] = message

        return request.render('amna_salih.ticket_portal_template', values)




