# -*- coding: utf-8 -*-
from openerp.report import report_sxw
from tools.translate import _
from datetime import datetime
from openerp.tools import misc
from osv import osv
import pytz


class BouquetReport(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(BouquetReport, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({'test_methode': self._test_methode,
                                  'displayLocaleDateTime': self._displayLocaleDateTime,
                                  })

    def _displayLocaleDateTime(self, timezone, format='%d/%m/%Y %H:%M', server_tz=None):
        try:
            if not server_tz:
                server_tz = misc.get_server_timezone()
            return pytz.timezone(server_tz).localize(datetime.now()).astimezone(
                pytz.timezone(timezone)).strftime(format)
        except:
            raise osv.except_osv(_('Timezone error or date format invalid!'),
                                 _('Please set your timezone before to generate this report.') +
                                 _(' One of those values is not valid: timezone= %r - format= %r')
                                 % (timezone, format))

    def _test_methode(self):
        return True

report_sxw.report_sxw('report.bouquet_webkit',
                      'anytracker.bouquet',
                      'anytracker/report/webkit_report/bouquet.mako',
                      parser=BouquetReport)
