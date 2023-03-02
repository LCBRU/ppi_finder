#!/usr/bin/env python

import argparse
import csv
import re
from datetime import datetime, date
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('inputfile', nargs=1, type=argparse.FileType('r'))
    parser.add_argument('-c', '--columns', nargs='*')
    parser.add_argument('-d', '--delimiter', nargs='?', default=',')
    parser.add_argument('--show_all_matches', action='store_true')
    
    args = parser.parse_args()

    # with open(args.inputfile[0], newline='') as csvfile:
    reader = csv.DictReader(args.inputfile[0], delimiter=args.delimiter)

    ppif = PpiFinder(columns=args.columns)

    result = ppif.analyse(reader)

    report = ''
    for c, r in result.items():
        report += found_message(c, 'UHL System Number', r, args.show_all_matches)
        report += found_message(c, 'postcode', r, args.show_all_matches)
        report += found_message(c, 'NHS Number', r, args.show_all_matches)
        report += found_message(c, 'Date of Birth', r, args.show_all_matches)
        if len(r['Name']) > 0:
            report += f'Column "{c}" may contain the names: {", ".join(r["Name"])}\n'

    print(report)

def found_message(column, ppi_name, result, show_all_matches):
    values = result[ppi_name]

    if len(values) > 0:
        if show_all_matches:
            values_values = ';\t'.join([f'Row {v["row"]}: {v["value"]}' for v in values])
            return f'Column "{column}" may contain a {ppi_name} in values:\n\n {values_values}\n'
        else:
            return f'Column "{column}" may contain a {ppi_name} first found in row {values[0]["row"]} in values: {values[0]["value"]}\n'
    else:
        return ''

class PpiFinder():
    re_numbers = re.compile(r'\d')
    re_words = re.compile(r'\W+')
    re_uhl_s_number = re.compile(r'([SRFG]\d{7}|[U]\d{7}.*|LB\d{7}|RTD[\-0-9]*)')
    re_postcodes = re.compile(r'([Gg][Ii][Rr] ?0[Aa]{2})|((([A-Za-z][0-9]{1,2})|(([A-Za-z][A-Ha-hJ-Yj-y][0-9]{1,2})|(([A-Za-z][0-9][A-Za-z])|([A-Za-z][A-Ha-hJ-Yj-y][0-9][A-Za-z]?))))\s?[0-9][A-Za-z]{2})')
    re_nhs_dividers = re.compile(r'[- ]')
    re_nhs_numbers = re.compile(r'\b(\d{10}|\d{3}-\d{3}-\d{4}|\d{3} \d{3} \d{4})\b')
    re_ansi_dates = re.compile(r'(?P<year>\d{4})[\\ -]?(?P<month>\d{2})[\\ -]?(?P<day>\d{2})(?:[ T]\d{2}:\d{2}:\d{2})?(?:\.\d+)?(?:[+-]\d{2}:\d{2})?')


    def __init__(self, columns=None):
        self.columns = columns

        with open('_names.txt', 'r') as f:
            self.names = {n for n in f.readlines()}

    def analyse(self, csv):

        cols = self.columns or csv.fieldnames

        errors = {c: {
            'UHL System Number': [],
            'postcode': [],
            'NHS Number': [],
            'Date of Birth': [],
            'Name': set(),
        } for c in cols}

        for i, row in enumerate(csv):
            if i % 1000 == 0:
                print(f"Analysed {i:,} rows")

            for c in cols:
                value = row[c]
                e = errors[c]

                if self.contains_uhl_system_number(value):
                    e['UHL System Number'].append({'row': i, 'value': value})
                if self.contains_postcode(value):
                    e['postcode'].append({'row': i, 'value': value})
                if self.contains_nhs_number(value):
                    e['NHS Number'].append({'row': i, 'value': value})
                if self.contains_dob(value):
                    e['Date of Birth'].append({'row': i, 'value': value})
                e['Name'].update(self.contains_name(value))

        return errors

    def contains_name(self, value):
        if not value or not isinstance(value, str):
            return set()

        value = self.re_numbers.sub(' ', value.lower())

        found = set()

        for w in self.re_words.split(value):
            if w in self.names:
                found.add(w)

        return found

    def contains_uhl_system_number(self, value):
        if not value or not isinstance(value, str):
            return False

        if self.re_uhl_s_number.search(value):
            return True

    def contains_postcode(self, value):
        if not value or not isinstance(value, str):
            return False

        if self.re_postcodes.search(value):
            return True

    def contains_nhs_number(self, value):
        if not value:
            return False

        if isinstance(value, str):
            # value = self.re_nhs_dividers.sub('', value)
            pass
        else:
            value = str(value)

        # A valid NHS number must be 10 digits long
        matches = self.re_nhs_numbers.findall(value)

        for m in matches:
            m = self.re_nhs_dividers.sub('', m)
            if self.calculate_nhs_number_checksum(m) == m[9]:
                return True

    def contains_dob(self, value):
        try:
            dt_val = self.parse_date(value)
        except:
            return False

        if not dt_val:
            return False

        if (datetime.utcnow().date() - relativedelta(years=130)) < dt_val < (datetime.utcnow().date() - relativedelta(years=10)):
            return True

    def calculate_nhs_number_checksum(self, nhs_number):
        checkcalc = lambda sum: 11 - (sum % 11)

        char_total = sum(
            [int(j) * (11 - (i + 1)) for i, j in enumerate(nhs_number[:9])]
        )
        return str(checkcalc(char_total)) if checkcalc(char_total) != 11 else '0'

    def parse_date(self, value):
        if not value:
            return None

        if isinstance(value, datetime):
            return value.date()

        if isinstance(value, date):
            return value

        value = str(value)

        ansi_match = self.re_ansi_dates.fullmatch(value)

        if ansi_match:
            return date(
                int(ansi_match.group('year')),
                int(ansi_match.group('month')),
                int(ansi_match.group('day')),
            )

        try:
            f = float(value)
            if not (1_000_000 < f < 100_000_000):
                return None
        except:
            pass


        parsed_date = parse(value, dayfirst=True)

        return parsed_date.date()


if __name__ == "__main__":
   main()