# -*- coding: utf-8 -
import logging
import json
from datetime import date, timedelta, datetime
from decimal import Decimal

log = logging.getLogger(__name__)

NAIVE_DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
DATE_FORMAT = '%Y-%m-%d'


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        try:
            return json.JSONEncoder.default(self, obj)
        except TypeError:
            if type(obj) is date:
                return obj.strftime(DATE_FORMAT)

            if type(obj) is datetime:
                return obj.strftime(NAIVE_DATETIME_FORMAT)

            if type(obj) is timedelta:
                # return it as rounded milliseconds
                return int(obj.total_seconds() * 1000)

            if type(obj) is Decimal:
                return str(obj)

            raise


def _get_logic_functions(module_root, logic_functions={}):
    '''
    Helper function that scans extension logic dir for all logic functions.
    '''
    for module_name in ['create', 'delete', 'get', 'patch', 'update']:
        module_path = '%s.%s' % (module_root, module_name,)

        module = __import__(module_path)

        for part in module_path.split('.')[1:]:
            module = getattr(module, part)

        for key, value in module.__dict__.items():
            if not key.startswith('_') and (hasattr(value, '__call__')
               and (value.__module__ == module_path)):
                logic_functions[key] = value

    return logic_functions


def remove_elements(row):
    """Removes elements that are not in columns"""
    try:
        row.pop('_id')
    except KeyError:
        pass
    try:
        row.pop('_full_count')
    except KeyError:
        pass
    try:
        row.pop('rank')
    except KeyError:
        pass


def replace(column):
    d = str(column[0])
    if d.isnumeric():
        column = '_' + column
    column = column.replace(" ", "_")
    column = column.replace("(", "")
    column = column.replace(")", "")
    column = column.replace("&", "&amp;")
    column = column.replace("<", "&lt;")
    column = column.replace(">", "&gt;")
    column = column.replace("\"", "&quot;")
    column = column.replace("'", "&apos;")
    return column
