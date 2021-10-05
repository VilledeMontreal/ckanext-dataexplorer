import logging
import json
import csv
from io import StringIO

from flask import Response
from werkzeug.wrappers import response

import ckan.logic as logic
from ckan.common import config, _
from xlsxwriter.workbook import Workbook
from xml.etree.cElementTree import Element, SubElement, ElementTree
from ckanext.dataexplorer.helpers import CustomJSONEncoder


DUMP_FORMATS = 'csv', 'json', 'xml', 'tsv'

UTF8_BOM = u'\uFEFF'.encode(u'utf-8')

log = logging.getLogger(__name__)


class XMLWriter(object):
    def __init__(self, output, columns):

        self.delimiter = config.get(
            'ckanext.dataexplorer.headers_names_delimiter', "_")
        self.output = output
        self.id_col = columns[0] == u'_id'
        if self.id_col:
            columns = columns[1:]
        columns_fixed = []
        for column in columns:
            columns_fixed.append(column.replace(" ", self.delimiter))
        self.columns = columns_fixed
        log.debug(self.columns)

    def writerow(self, row):
        root = Element(u'row')
        if self.id_col:
            root.attrib[u'_id'] = str(row[0])
            row = row[1:]
        for k, v in zip(self.columns, row):
            if v is None:
                SubElement(root, k).text = u'NULL'
                continue
            SubElement(root, k).text = str(v)
        ElementTree(root).write(self.output, encoding=u'utf-8')
        self.output.write(b'\n')


class JSONWriter(object):
    def __init__(self, columns, data):
        self.output = StringIO()
        self.columns = columns
        self.first = True
        self.n = len(data)
        self.output.write(
            '{\n  "fields": %s,\n  "records": [' %
            json.dumps(columns, ensure_ascii=False, separators=(',', ':')))

    def writerow(self, data):
        for index, json_line in enumerate(data):
            if self.first:
                self.first = False
                self.output.write('\n   ')
            else:
                self.output.write(',\n  ')
            self.output.write(json.dumps(
                    json_line,
                    indent=8,
                    ensure_ascii=False,
                    separators=(u',', u':'),
                    sort_keys=True,
                    cls=CustomJSONEncoder))
            if index == (self.n - 1):
                self.finish()
            yield self.output.getvalue()
            self.output.truncate(0)
            self.output.seek(0)

    def finish(self):
        self.output.write('\n]}\n')


class UnicodeCSVWriter:
    """
    A CSV writer which will write rows to CSV file
    """

    def iter_csv(columns, data, delimiter=','):
        line = StringIO()
        writer = csv.writer(line, delimiter=delimiter)
        writer.writerow(columns)
        for csv_line in data:
            csv_line = csv_line.values()
            writer.writerow(csv_line)
            line.seek(0)
            yield line.read()
            line.truncate(0)
            line.seek(0)


class FileWriterService():
    def _tsv_writer(self, columns, records, name):
        response = Response(UnicodeCSVWriter.iter_csv(columns,
                                                      records,
                                                      delimiter='\t'),
                            mimetype='text/csv')
        response.headers['Content-Type'] = b'text/tsv; charset=utf-8'
        if name:
            response.headers['Content-disposition'] = bytes(
                'attachment; filename="{name}.tsv"'.format(
                    name=name), encoding='utf8')

        return response

    def _csv_writer(self, columns, records, name):
        response = Response(UnicodeCSVWriter.iter_csv(columns,
                                                      records,
                                                      delimiter=','),
                            mimetype='text/csv')
        response.headers['Content-Type'] = b'text/csv; charset=utf-8'
        if name:
            response.headers['Content-disposition'] = bytes(
                'attachment; filename="{name}.csv"'.format(
                    name=name), encoding='utf8')

        return response

    def _json_writer(self, columns, records, name):
        json_obj = JSONWriter(columns, records)
        response = Response(json_obj.writerow(records),
                            mimetype='application/json')

        response.headers['Content-Type'] = (b'application/json; charset=utf-8')
        if name:
            response.headers['Content-disposition'] = bytes(
                'attachment; filename="{name}.json"'.format(
                    name=name), encoding='utf8')

        return response

    def _xml_writer(self, columns, records, response, name):

        if hasattr(response, u'headers'):
            response.headers['Content-Type'] = (
                b'text/xml; charset=utf-8')
            if name:
                response.headers['Content-disposition'] = (
                    b'attachment; filename="{name}.xml"'.format(
                        name=name.encode('utf-8')))

        response.write(b'<data>\n')

        # Initiate xml writer and columns
        wr = XMLWriter(response, [c.encode("utf-8") for c in columns])

        # Write records
        for record in records:
            wr.writerow([record[column] for column in columns])

        response.write(b'</data>\n')

    def _xlsx_writer(self, columns, records, response, name):

        output = StringIO()

        if hasattr(response, u'headers'):
            response.headers['Content-Type'] = (
                b'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;\
                    charset=utf-8')
            if name:
                response.headers['Content-disposition'] = (
                    b'attachment; filename="{name}.xlsx"'.format(
                        name=name.encode('utf-8')))

        workbook = Workbook(output)
        worksheet = workbook.add_worksheet()

        # Writing headers
        col = 0
        for c in columns:
            worksheet.write(0, col, c)
            col += 1

        # Writing records
        row = 1
        for record in records:
            col = 0
            for column in columns:
                worksheet.write(row, col, record[column])
                col += 1
            row += 1

        workbook.close()
        response.write(output.getvalue())

    def write_to_file(self, columns, records, format, name):

        format = format.lower()
        if format == 'csv':
            return self._csv_writer(columns, records, name)
        if format == 'json':
            return self._json_writer(columns, records, name)
        if format == 'xml':
            return self._xml_writer(columns, records, response, name)
        if format == 'tsv':
            return self._tsv_writer(columns, records, name)
        raise logic.ValidationError(_(
            u'format: must be one of %s') % u', '.join(DUMP_FORMATS))
