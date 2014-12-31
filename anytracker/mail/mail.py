# coding:utf-8
from openerp.osv import osv


class MailMail(osv.Model):

    _inherit = 'mail.mail'

    def create(self, cr, uid, values, context=None):
        """ override to use 'anytracker@anybox.fr' as 'reply to' address
            when sending mail from anytracker.ticket model """
        if(context and 'default_model' in context
           and context['default_model'] == 'anytracker.ticket'):
            values.update(reply_to='anytracker@anybox.fr')
        return super(MailMail, self).create(cr, uid, values, context=context)
