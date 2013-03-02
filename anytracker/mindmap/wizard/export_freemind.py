from osv import osv, fields
import random
import time
from xml.sax.saxutils import XMLGenerator


#TODO complexity icon, mindmapfile to binary?, richtext content generation
class export_freemind_wizard(osv.TransientModel):
    _name = 'export.freemind.wizard'
    _description = 'export freemind .mm file for generate by anytracker tree'
    _columns = {
        'ticket_id': fields.many2one('anytracker.ticket', 'Ticket'),
        'mindmap_file': fields.char('Path of file to write', 256),
        'green_complexity': fields.many2one('anytracker.complexity', 'green complexity'),
        'orange_complexity': fields.many2one('anytracker.complexity', 'orange complexity'),
        'red_complexity': fields.many2one('anytracker.complexity', 'red complexity'),
    }

    def execute_export(self, cr, uid, ids, context=None):
        '''Launch export of nn file to freemind'''
        any_tick_complexity_pool = self.pool.get('anytracker.complexity')
        for wizard in self.browse(cr, uid, ids, context=context):
            complexity_dict = {
                'green_complexity_id':
                wizard.green_complexity.id
                or any_tick_complexity_pool.search(cr, uid, [('value', '=', 3)])[0],
                'orange_complexity_id': wizard.orange_complexity.id
                or any_tick_complexity_pool.search(cr, uid, [('value', '=', 21)])[0],
                'red_complexity_id': wizard.red_complexity.id
                or any_tick_complexity_pool.search(cr, uid, [('value', '=', 3)])[0],
            }
            ticket_id = wizard.ticket_id and wizard.ticket_id.id or False
            if not ticket_id:
                raise osv.except_osv('Error', 'Please select a ticket to export')
            fp = open(wizard.mindmap_file, 'wb')
            writer_handler = FreemindWriterHandler(cr, uid, self.pool, fp)
            writer_parser = FreemindParser(cr, uid, self.pool, writer_handler,
                                           ticket_id, complexity_dict)
            writer_parser.parse(cr, uid)
            fp.close()
        return {'type': 'ir.actions.act_window_close'}


class FreemindParser(object):
    '''Parse openerp project'''
    def __init__(self, cr, uid, pool, handler, ticket_id, complexity_dict):
        self.handler = handler
        self.pool = pool
        self.ticket_id = ticket_id
        self.complexity_dict = complexity_dict

    def parse(self, cr, uid):
        ticket_osv = self.pool.get('anytracker.ticket')
        self.handler.startDocument()
        ticket_tree_ids = ticket_osv.makeTreeData(cr, uid, [self.ticket_id])

        def recurs_ticket(ticket_d):
            ticket_write = ticket_d.copy()
            if 'child' in ticket_write:
                ticket_write.pop('child')
            self.handler.startElement('node', ticket_write)
            if 'child' in ticket_d:
                for ticket in ticket_d['child']:
                    recurs_ticket(ticket)
            self.handler.endElement('node')
        recurs_ticket(ticket_tree_ids[0])
        self.handler.endDocument()
        return True


def gMF(date):
    '''getMindmapDateFormat

    input: OpenERP string date/time format
    output: str of decimal representation of Epoch-based timestamp milliseconds, rounded.
    '''
    timestamp = time.mktime(time.strptime(date, '%Y-%m-%d %H:%M:%S')) if date else time.time()
    return '%d' % (timestamp * 1000)


class FreemindWriterHandler(XMLGenerator):
    '''For generate .mm file'''
    def __init__(self, cr, uid, pool, fp):
        self.pool = pool
        self.padding = 0
        XMLGenerator.__init__(self, fp, 'UTF-8')
        #super(FreemindWriterHandler, self).__init__(fp)

    def startDocument(self):
        startElement = '''<map version="0.9.0">
<!-- To view this file, download FreeMind from http://freemind.sourceforge.net -->
'''
        self._out.write(startElement)

    def endDocument(self):
        stopElement = '</' + 'map' + '>' + '\n'
        self._out.write(stopElement)

    def startElement(self, tag, attrs={}):
        attrs_write = {'CREATED': gMF(attrs['created_mindmap']),
                       'MODIFIED': gMF(max(attrs['modified_mindmap'],
                                           attrs['modified_openerp'])),
                       'ID': attrs['id_mindmap'] or 'ID_' + str(random.randint(1, 10**10)),
                       'TEXT': attrs['name'],
                       }
        XMLGenerator.startElement(self, tag, attrs_write)
        #super(FreemindWriterHandler, self).startElement(tag, attrs_write)

    def endElement(self, tag):
        XMLGenerator.endElement(self, tag)
